from collections import namedtuple
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.elastic import send_to_elasticsearch
from corehq.apps.es import UserES
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.group import get_group_to_elasticsearch_processor
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint, get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import PillowChangeProviderReindexer, ReindexerFactory


class GroupsToUsersProcessor(PillowProcessor):
    """When a group changes, this updates the user doc in UserES

    Reads from:
      - Kafka topics: group
      - Group data source (CouchDB)

    Writes to:
      - UserES index
    """

    def process_change(self, change):
        if change.deleted:
            remove_group_from_users(change.get_document())
        else:
            update_es_user_with_groups(change.get_document())


def get_group_to_user_pillow(pillow_id='GroupToUserPillow', num_processes=1, process_num=0, **kwargs):
    """Group pillow that updates user data in Elasticsearch with group membership

    Processors:
      - :py:class:`corehq.pillows.groups_to_user.GroupsToUsersProcessor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    assert pillow_id == 'GroupToUserPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, USER_INDEX_INFO, [topics.GROUP])
    processor = GroupsToUsersProcessor()
    change_feed = KafkaChangeFeed(
        topics=[topics.GROUP], client_id='groups-to-users', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=10, change_feed=change_feed
        ),
    )


def get_group_pillow(pillow_id='group-pillow', num_processes=1, process_num=0, **kwargs):
    """Group pillow

    Processors:
      - :py:class:`corehq.pillows.groups_to_user.GroupsToUsersProcessor`
      - :py:func:`corehq.pillows.group.get_group_to_elasticsearch_processor`
    """
    assert pillow_id == 'group-pillow', 'Pillow ID is not allowed to change'
    to_user_es_processor = GroupsToUsersProcessor()
    to_group_es_processor = get_group_to_elasticsearch_processor()
    change_feed = KafkaChangeFeed(
        topics=[topics.GROUP], client_id='groups-to-users', num_processes=num_processes, process_num=process_num
    )
    checkpoint_id = "{}-{}-{}".format(
        pillow_id, USER_INDEX, to_group_es_processor.index_info.index)
    checkpoint = KafkaPillowCheckpoint(checkpoint_id, [topics.GROUP])
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=[to_user_es_processor, to_group_es_processor],
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=10, change_feed=change_feed
        ),
    )


def remove_group_from_users(group_doc):
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
            doc["_id"] = user_source.user_id
            send_to_elasticsearch('users', doc, es_merge_update=True)


def update_es_user_with_groups(group_doc):
    for user_source in stream_user_sources(group_doc.get("users", [])):
        if group_doc["name"] not in user_source.group_names or group_doc["_id"] not in user_source.group_ids:
            user_source.group_ids.add(group_doc["_id"])
            user_source.group_names.add(group_doc["name"])
            doc = {"__group_ids": list(user_source.group_ids), "__group_names": list(user_source.group_names)}
            doc["_id"] = user_source.user_id
            send_to_elasticsearch('users', doc, es_merge_update=True)

    for user_source in stream_user_sources(group_doc.get("removed_users", [])):
        if group_doc["name"] in user_source.group_names or group_doc["_id"] in user_source.group_ids:
            user_source.group_ids.remove(group_doc["_id"])
            user_source.group_names.remove(group_doc["name"])
            doc = {"__group_ids": list(user_source.group_ids), "__group_names": list(user_source.group_names)}
            doc["_id"] = user_source.user_id
            send_to_elasticsearch('users', doc, es_merge_update=True)



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
            pillow_or_processor=get_group_to_user_pillow(),
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
