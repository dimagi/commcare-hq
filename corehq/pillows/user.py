import copy
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.es.users import user_adapter
from corehq.apps.groups.dbaccessors import get_group_id_name_map_by_user
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.pillow import get_ucr_processor
from corehq.util.quickcache import quickcache
from corehq.util.doc_processor.couch import CouchDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor, PillowProcessor
from pillowtop.processors.elastic import BulkElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer
from pillowtop.reindexer.reindexer import ReindexerFactory


def update_unknown_user_from_form_if_necessary(doc_dict):
    if doc_dict is None:
        return

    user_id, username, domain, xform_id = _get_user_fields_from_form_doc(doc_dict)

    if (not user_id
            or user_id in WEIRD_USER_IDS
            or _user_exists_in_couch(user_id)):
        return

    if not user_adapter.exists(user_id):
        doc_type = "AdminUser" if username == "admin" else "UnknownUser"
        doc = {
            "_id": user_id,
            "domain": domain,
            "username": username,
            "first_form_found_in": xform_id,
            "doc_type": doc_type,
        }
        if domain:
            doc["domain_membership"] = {"domain": domain}
        user_adapter.index(doc)


@quickcache(['user_id'])
def _user_exists_in_couch(user_id):
    return CouchUser.get_db().doc_exist(user_id)


def _get_user_fields_from_form_doc(form_doc):
    form_meta = form_doc.get('form', {}).get('meta', {})
    domain = form_doc.get('domain')
    user_id = form_meta.get('userID')
    username = form_meta.get('username')
    xform_id = form_doc.get('_id')
    return user_id, username, domain, xform_id


class UnknownUsersProcessor(PillowProcessor):
    """Monitors forms for user_ids we don't know about and creates an entry in ES for the user.

    Reads from:
      - Kafka topics: form-sql, form
      - XForm data source

    Writes to:
      - UserES index
    """

    def process_change(self, change):
        update_unknown_user_from_form_if_necessary(change.get_document())


def add_demo_user_to_user_index():
    user_adapter.index(
        {"_id": "demo_user", "username": "demo_user", "doc_type": "DemoUser"}
    )


def get_user_es_processor():
    return BulkElasticProcessor(user_adapter)


def get_user_pillow_old(pillow_id='UserPillow', num_processes=1, process_num=0, **kwargs):
    """Processes users and sends them to ES.

    Processors:
      - :py:func:`pillowtop.processors.elastic.ElasticProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'UserPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, user_adapter.index_name, topics.USER_TOPICS)
    user_processor = ElasticProcessor(user_adapter)
    change_feed = KafkaChangeFeed(
        topics=topics.USER_TOPICS, client_id='users-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=user_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


def get_user_pillow(pillow_id='user-pillow', num_processes=1, dedicated_migration_process=False, process_num=0,
        skip_ucr=False, processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    """Processes users and sends them to ES and UCRs.

    Processors:
      - :py:func:`pillowtop.processors.elastic.BulkElasticProcessor`
      - :py:func:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
    """
    # Pillow that sends users to ES and UCR
    assert pillow_id == 'user-pillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, user_adapter.index_name, topics.USER_TOPICS)
    user_processor = get_user_es_processor()
    ucr_processor = get_ucr_processor(
        data_source_providers=[
            DynamicDataSourceProvider('CommCareUser'),
            StaticDataSourceProvider('CommCareUser')
        ],
        run_migrations=(process_num == 0),  # only first process runs migrations,
    )
    change_feed = KafkaChangeFeed(
        topics=topics.USER_TOPICS, client_id='users-to-es', num_processes=num_processes, process_num=process_num,
        dedicated_migration_process=dedicated_migration_process
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=[user_processor] if skip_ucr else [ucr_processor, user_processor],
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
        processor_chunk_size=processor_chunk_size,
        process_num=process_num,
        is_dedicated_migration_process=dedicated_migration_process and (process_num == 0)
    )


def get_unknown_users_pillow(pillow_id='unknown-users-pillow', num_processes=1, process_num=0, **kwargs):
    """This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ

        Processors:
          - :py:class:`corehq.pillows.user.UnknownUsersProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, user_adapter.index_name, topics.FORM_TOPICS)
    processor = UnknownUsersProcessor()
    change_feed = KafkaChangeFeed(
        topics=topics.FORM_TOPICS, client_id='unknown-users', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


class UserReindexerFactory(ReindexerFactory):
    slug = 'user'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args
    ]

    def build(self):
        iteration_key = "UserToElasticsearchPillow_{}_reindexer".format(user_adapter.index_name)
        doc_provider = CouchDocumentProvider(iteration_key, [CommCareUser, WebUser])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            user_adapter,
            pillow=get_user_pillow_old(),
            **options
        )
