from collections import namedtuple
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document, GROUP
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.elastic import stream_es_query, get_es_new, ES_META
from corehq.pillows.mappings.user_mapping import USER_INDEX
from pillowtop.checkpoints.manager import get_default_django_checkpoint_for_legacy_pillow_class, PillowCheckpoint, \
    PillowCheckpointEventHandler
from pillowtop.listener import PythonPillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import PillowReindexer


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


class GroupsToUsersProcessor(PillowProcessor):
    def __init__(self):
        self._es = get_es_new()

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        if change.deleted:
            remove_group_from_users(change.get_document(), self._es)
        else:
            update_es_user_with_groups(change.get_document(), self._es)


def get_group_to_user_pillow(pillow_id='GroupToUserPillow'):
    checkpoint = PillowCheckpoint(
        pillow_id,
    )
    processor = GroupsToUsersProcessor()
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[GROUP], group_id='groups-to-users'),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


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


def get_groups_to_user_reindexer():
    return PillowReindexer(
        pillow=get_group_to_user_pillow(),
        change_provider=CouchViewChangeProvider(
            couch_db=Group.get_db(),
            view_name='all_docs/by_doc_type',
            view_kwargs={
                'startkey': ['Group'],
                'endkey': ['Group', {}],
                'include_docs': True,
            }
        ),
    )
