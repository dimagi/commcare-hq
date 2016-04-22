from collections import namedtuple
from casexml.apps.case.xform import is_device_report
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.document_types import COMMCARE_USER, WEB_USER, get_doc_meta_object_from_document, \
    GROUP
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import WEIRD_USER_IDS
from corehq.elastic import (
    stream_es_query, doc_exists_in_es,
    send_to_elasticsearch, get_es_new, ES_META
)
from corehq.pillows.mappings.user_mapping import USER_MAPPING, USER_INDEX, USER_META, USER_INDEX_INFO
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from dimagi.utils.decorators.memoized import memoized
from pillowtop.checkpoints.manager import get_default_django_checkpoint_for_legacy_pillow_class, PillowCheckpoint, \
    PillowCheckpointEventHandler
from pillowtop.listener import AliasedElasticPillow, PythonPillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


class UserPillow(AliasedElasticPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = CommCareUser   # while this index includes all users,
                                    # I assume we don't care about querying on properties specific to WebUsers
    couch_filter = "users/all_users"
    es_timeout = 60
    es_alias = "hqusers"
    es_type = "user"
    es_meta = USER_META
    es_index = USER_INDEX
    default_mapping = USER_MAPPING

    @classmethod
    def get_unique_id(self):
        return USER_INDEX


class GroupToUserPillow(PythonPillow):
    document_class = CommCareUser

    def __init__(self):
        checkpoint = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(GroupToUserPillow, self).__init__(checkpoint=checkpoint)
        self.es = get_es_new()
        self.es_type = ES_META['users'].type

    def python_filter(self, change):
        doc_meta = get_doc_meta_object_from_document(change.get_document())
        return doc_meta and doc_meta.primary_type == GROUP

    def change_transport(self, doc_dict):
        doc_meta = get_doc_meta_object_from_document(doc_dict)
        if doc_meta.is_deletion:
            remove_group_from_users(doc_dict, self.es)
        else:
            update_es_user_with_groups(doc_dict, self.es)


def remove_group_from_users(group_doc, es_client):
    for user_source in stream_user_sources(group_doc.get("users", [])):
        if group_doc["name"] in user_source.group_names or group_doc["_id"] in user_source.group_ids:
            user_source.group_ids.remove(group_doc["_id"])
            user_source.group_names.remove(group_doc["name"])
            doc = {"__group_ids": list(user_source.group_ids), "__group_names": list(user_source.group_names)}
            es_client.update(USER_INDEX, ES_META['users'].type, user_source.user_id, body={"doc": doc})


def update_es_user_with_groups(group_doc, es_client=None):
    if not es_client:
        es_client = get_es_new()

    for user_source in stream_user_sources(group_doc.get("users", [])):
        if group_doc["name"] not in user_source.group_names or group_doc["_id"] not in user_source.group_ids:
            user_source.group_ids.add(group_doc["_id"])
            user_source.group_names.add(group_doc["name"])
            doc = {"__group_ids": list(user_source.group_ids), "__group_names": list(user_source.group_names)}
            es_client.update(USER_INDEX, ES_META['users'].type, user_source.user_id, body={"doc": doc})


UserSource = namedtuple('UserSource', ['user_id', 'group_ids', 'group_names'])


def stream_user_sources(user_ids):
    q = {"filter": {"and": [{"terms": {"_id": user_ids}}]}}
    for result in stream_es_query(es_index='users', q=q, fields=["__group_ids", "__group_names"]):
        group_ids = result.get('fields', {}).get("__group_ids", [])
        group_ids = set(group_ids) if isinstance(group_ids, list) else {group_ids}
        group_names = result.get('fields', {}).get("__group_names", [])
        group_names = set(group_names) if isinstance(group_names, list) else {group_names}
        yield UserSource(result['_id'], group_ids, group_names)


class UnknownUsersPillow(PythonPillow):
    """
    This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    document_class = XFormInstance

    def __init__(self):
        checkpoint = get_default_django_checkpoint_for_legacy_pillow_class(self.__class__)
        super(UnknownUsersPillow, self).__init__(checkpoint=checkpoint)
        self.user_db = CouchUser.get_db()
        self.es = get_es_new()
        self.es_type = ES_META['users'].type

    def python_filter(self, change):
        # designed to exactly mimic the behavior of couchforms/filters/xforms.js
        doc = change.get_document()
        return doc and doc.get('doc_type', None) in all_known_formlike_doc_types() and not is_device_report(doc)

    def get_fields_from_doc(self, doc):
        form_meta = doc.get('form', {}).get('meta', {})
        domain = doc.get('domain')
        user_id = form_meta.get('userID')
        username = form_meta.get('username')
        xform_id = doc.get('_id')
        return user_id, username, domain, xform_id

    @memoized
    def _user_exists(self, user_id):
        return self.user_db.doc_exist(user_id)

    def _user_indexed(self, user_id):
        return doc_exists_in_es('users', user_id)

    def change_transport(self, doc_dict):
        doc = doc_dict
        user_id, username, domain, xform_id = self.get_fields_from_doc(doc)

        if user_id in WEIRD_USER_IDS:
            user_id = None

        if (user_id and not self._user_exists(user_id)
                and not self._user_indexed(user_id)):
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
            self.es.create(USER_INDEX, self.es_type, body=doc, id=user_id)


def add_demo_user_to_user_index():
    send_to_elasticsearch(
        'users',
        {"_id": "demo_user", "username": "demo_user", "doc_type": "DemoUser"}
    )


def get_user_kafka_to_elasticsearch_pillow(pillow_id='user-kafka-to-es'):
    checkpoint = PillowCheckpoint(
        pillow_id,
    )
    domain_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=USER_INDEX_INFO,
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[COMMCARE_USER, WEB_USER], group_id='users-to-es'),
        processor=domain_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_user_reindexer():
    return ElasticPillowReindexer(
        pillow=get_user_kafka_to_elasticsearch_pillow(),
        change_provider=CouchViewChangeProvider(
            couch_db=CommCareUser.get_db(),
            view_name='users/by_username',
            view_kwargs={
                'include_docs': True,
            }
        ),
        elasticsearch=get_es_new(),
        index_info=USER_INDEX_INFO,
    )
