import copy
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.dbaccessors import get_group_id_name_map_by_user
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.pillow import ConfigurableReportPillowProcessor
from corehq.elastic import (
    doc_exists_in_es,
    send_to_elasticsearch, get_es_new, ES_META
)
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.quickcache import quickcache
from corehq.util.doc_processor.couch import CouchDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.const import DEFAULT_PROCESSOR_CHUNK_SIZE
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor, PillowProcessor
from pillowtop.processors.elastic import BulkElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer
from pillowtop.reindexer.reindexer import ReindexerFactory


def update_unknown_user_from_form_if_necessary(es, doc_dict):
    if doc_dict is None:
        return

    user_id, username, domain, xform_id = _get_user_fields_from_form_doc(doc_dict)

    if (not user_id
            or user_id in WEIRD_USER_IDS
            or _user_exists_in_couch(user_id)):
        return

    if not doc_exists_in_es(USER_INDEX_INFO, user_id):
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
        ElasticsearchInterface(es).create_doc(USER_INDEX_INFO.alias, ES_META['users'].type, doc=doc, doc_id=user_id)


def transform_user_for_elasticsearch(doc_dict):
    doc = copy.deepcopy(doc_dict)
    if doc['doc_type'] == 'CommCareUser' and '@' in doc['username']:
        doc['base_username'] = doc['username'].split("@")[0]
    else:
        doc['base_username'] = doc['username']

    results = get_group_id_name_map_by_user(doc['_id'])
    doc['__group_ids'] = [res.id for res in results]
    doc['__group_names'] = [res.name for res in results]
    doc['user_data_es'] = []
    if 'user_data' in doc:
        for key, value in doc['user_data'].items():
            doc['user_data_es'].append({
                'key': key,
                'value': value,
            })
    return doc


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

    def __init__(self):
        self._es = get_es_new()

    def process_change(self, change):
        update_unknown_user_from_form_if_necessary(self._es, change.get_document())


def add_demo_user_to_user_index():
    send_to_elasticsearch(
        'users',
        {"_id": "demo_user", "username": "demo_user", "doc_type": "DemoUser"}
    )


def get_user_es_processor():
    return BulkElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=USER_INDEX_INFO,
        doc_prep_fn=transform_user_for_elasticsearch,
    )


def get_user_pillow_old(pillow_id='UserPillow', num_processes=1, process_num=0, **kwargs):
    """Processes users and sends them to ES.

    Processors:
      - :py:func:`pillowtop.processors.elastic.ElasticProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'UserPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, topics.USER_TOPICS)
    user_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=USER_INDEX_INFO,
        doc_prep_fn=transform_user_for_elasticsearch,
    )
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


def get_user_pillow(pillow_id='user-pillow', num_processes=1, process_num=0,
        skip_ucr=False, processor_chunk_size=DEFAULT_PROCESSOR_CHUNK_SIZE, **kwargs):
    """Processes users and sends them to ES and UCRs.

    Processors:
      - :py:func:`pillowtop.processors.elastic.BulkElasticProcessor`
      - :py:func:`corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor`
    """
    # Pillow that sends users to ES and UCR
    assert pillow_id == 'user-pillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, topics.USER_TOPICS)
    user_processor = get_user_es_processor()
    ucr_processor = ConfigurableReportPillowProcessor(
        data_source_providers=[DynamicDataSourceProvider('CommCareUser'), StaticDataSourceProvider('CommCareUser')],
        run_migrations=(process_num == 0),  # only first process runs migrations
    )
    change_feed = KafkaChangeFeed(
        topics=topics.USER_TOPICS, client_id='users-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=[user_processor] if skip_ucr else [ucr_processor, user_processor],
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
        processor_chunk_size=processor_chunk_size
    )


def get_unknown_users_pillow(pillow_id='unknown-users-pillow', num_processes=1, process_num=0, **kwargs):
    """This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ

        Processors:
          - :py:class:`corehq.pillows.user.UnknownUsersProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, topics.FORM_TOPICS)
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
        iteration_key = "UserToElasticsearchPillow_{}_reindexer".format(USER_INDEX)
        doc_provider = CouchDocumentProvider(iteration_key, [CommCareUser, WebUser])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=USER_INDEX_INFO,
            doc_transform=transform_user_for_elasticsearch,
            pillow=get_user_pillow_old(),
            **options
        )
