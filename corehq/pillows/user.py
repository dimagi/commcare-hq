from __future__ import absolute_import
from __future__ import unicode_literals
import copy
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.apps.userreports.data_source_providers import DynamicDataSourceProvider, StaticDataSourceProvider
from corehq.apps.userreports.pillow import ConfigurableReportPillowProcessor
from corehq.elastic import (
    doc_exists_in_es,
    send_to_elasticsearch, get_es_new, ES_META
)
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.util.quickcache import quickcache
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor, PillowProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory
import six


def update_unknown_user_from_form_if_necessary(es, doc_dict):
    if doc_dict is None:
        return

    user_id, username, domain, xform_id = _get_user_fields_from_form_doc(doc_dict)

    if user_id in WEIRD_USER_IDS:
        user_id = None

    if (user_id and not _user_exists(user_id)
            and not doc_exists_in_es(USER_INDEX_INFO, user_id)):
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
        es.create(USER_INDEX, ES_META['users'].type, body=doc, id=user_id)


def transform_user_for_elasticsearch(doc_dict):
    doc = copy.deepcopy(doc_dict)
    if doc['doc_type'] == 'CommCareUser' and '@' in doc['username']:
        doc['base_username'] = doc['username'].split("@")[0]
    else:
        doc['base_username'] = doc['username']
    groups = Group.by_user(doc['_id'], wrap=False, include_names=True)
    doc['__group_ids'] = [group['group_id'] for group in groups]
    doc['__group_names'] = [group['name'] for group in groups]
    doc['user_data_es'] = []
    if 'user_data' in doc:
        for key, value in six.iteritems(doc['user_data']):
            doc['user_data_es'].append({
                'key': key,
                'value': value,
            })
    return doc


@quickcache(['user_id'])
def _user_exists(user_id):
    return CouchUser.get_db().doc_exist(user_id)


def _get_user_fields_from_form_doc(form_doc):
    form_meta = form_doc.get('form', {}).get('meta', {})
    domain = form_doc.get('domain')
    user_id = form_meta.get('userID')
    username = form_meta.get('username')
    xform_id = form_doc.get('_id')
    return user_id, username, domain, xform_id


class UnknownUsersProcessor(PillowProcessor):

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
    return ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=USER_INDEX_INFO,
        doc_prep_fn=transform_user_for_elasticsearch,
    )


def get_user_pillow_old(pillow_id='UserPillow', num_processes=1, process_num=0, **kwargs):
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
        skip_ucr=False, **kwargs):
    # Pillow that sends users to ES and UCR
    assert pillow_id == 'user-pillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, topics.USER_TOPICS)
    user_processor = get_user_es_processor()
    ucr_processor = ConfigurableReportPillowProcessor(
        data_source_providers=[DynamicDataSourceProvider('CommCareUser'), StaticDataSourceProvider('CommCareUser')],
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
    )


def get_unknown_users_pillow(pillow_id='unknown-users-pillow', num_processes=1, process_num=0, **kwargs):
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
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
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        return ElasticPillowReindexer(
            pillow_or_processor=get_user_pillow_old(),
            change_provider=CouchViewChangeProvider(
                couch_db=CommCareUser.get_db(),
                view_name='users/by_username',
                view_kwargs={
                    'include_docs': True,
                }
            ),
            elasticsearch=get_es_new(),
            index_info=USER_INDEX_INFO,
            **self.options
        )
