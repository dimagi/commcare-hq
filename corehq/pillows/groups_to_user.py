from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.elastic import stream_es_query, get_es_new, ES_META
from corehq.apps.es import UserES
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import PillowChangeProviderReindexer, ReindexerFactory


class GroupsToUsersProcessor(PillowProcessor):

    def __init__(self):
        self._es = get_es_new()

    def process_change(self, pillow_instance, change):
        if change.deleted:
            remove_group_from_users(change.get_document(), self._es)
        else:
            update_es_user_with_groups(change.get_document(), self._es)


def get_group_to_user_pillow(pillow_id='GroupToUserPillow', num_processes=1, process_num=0, **kwargs):
    assert pillow_id == 'GroupToUserPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, [topics.GROUP])
    processor = GroupsToUsersProcessor()
    change_feed = KafkaChangeFeed(
        topics=[topics.GROUP], group_id='groups-to-users', num_processes=num_processes, process_num=process_num
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


def remove_group_from_users(group_doc, es_client):
    if group_doc is None:
        return

    for user_source in stream_user_sources(group_doc.get("users", [])):
        made_changes = False
        if group_doc["name"] in user_source.group_names:
            user_source.group_names.remove(group_doc["name"])
            made_changes = True
        if group_doc["_id"] in user_source.group_ids:
            user_source.group_ids.remove(group_doc["_id"])
            made_changes = True
        if made_changes:
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

    for user_source in stream_user_sources(group_doc.get("removed_users", [])):
        if group_doc["name"] in user_source.group_names or group_doc["_id"] in user_source.group_ids:
            user_source.group_ids.remove(group_doc["_id"])
            user_source.group_names.remove(group_doc["name"])
            doc = {"__group_ids": list(user_source.group_ids), "__group_names": list(user_source.group_names)}
            es_client.update(USER_INDEX, ES_META['users'].type, user_source.user_id, body={"doc": doc})


UserSource = namedtuple('UserSource', ['user_id', 'group_ids', 'group_names'])


def stream_user_sources(user_ids):
    results = (
        UserES()
        .user_ids(user_ids)
        .fields(['_id', '__group_ids', '__group_names'])
        .scroll()
    )

    for result in results:
        group_ids = result.get('__group_ids', [])
        group_ids = set(group_ids) if isinstance(group_ids, list) else {group_ids}
        group_names = result.get('__group_names', [])
        group_names = set(group_names) if isinstance(group_names, list) else {group_names}
        yield UserSource(result['_id'], group_ids, group_names)


class GroupToUserReindexerFactory(ReindexerFactory):
    slug = 'groups-to-user'

    def build(self):
        return PillowChangeProviderReindexer(
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
