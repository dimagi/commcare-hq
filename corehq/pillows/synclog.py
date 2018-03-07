from __future__ import absolute_import
from __future__ import print_function

from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclogs_for_user
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.receiverwrapper.util import get_version_and_app_from_build_id
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
from corehq.apps.users.util import update_latest_builds, update_last_sync
from corehq.util.doc_processor.interface import BaseDocProcessor, DocumentProcessorController
from corehq.util.doc_processor.couch import CouchDocumentProvider

from dimagi.utils.parsing import string_to_utc_datetime

from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.interface import PillowProcessor
from pillowtop.feed.interface import Change
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.reindexer.reindexer import Reindexer, ReindexerFactory


SYNCLOG_SQL_USER_SYNC_GROUP_ID = "synclog_sql_user_sync"


def get_user_sync_history_pillow(
        pillow_id='UpdateUserSyncHistoryPillow', num_processes=1, process_num=0, **kwargs):
    """
    This gets a pillow which iterates through all synclogs
    """
    change_feed = KafkaChangeFeed(
        topics=[topics.SYNCLOG_SQL], group_id=SYNCLOG_SQL_USER_SYNC_GROUP_ID,
        num_processes=num_processes, process_num=process_num)
    checkpoint = KafkaPillowCheckpoint(pillow_id, [topics.SYNCLOG_SQL])
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=UserSyncHistoryProcessor(),
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


class UserSyncHistoryProcessor(PillowProcessor):

    def process_change(self, pillow_instance, change):
        synclog = change.get_document()
        if not synclog:
            return

        version = None
        app_id = None
        try:
            sync_date = string_to_utc_datetime(synclog.get('date'))
        except (ValueError, AttributeError):
            return
        build_id = synclog.get('build_id')
        if build_id:
            version, app_id = get_version_and_app_from_build_id(synclog.get('domain'), build_id)
        user_id = synclog.get('user_id')

        if user_id:
            user = CouchUser.get_by_user_id(user_id)
            save = update_last_sync(user, app_id, sync_date, version)
            if version:
                save |= update_latest_builds(user, app_id, sync_date, version)
            if save:
                user.save()


class UserSyncHistoryReindexerDocProcessor(BaseDocProcessor):

    def __init__(self, pillow_processor):
        self.pillow_processor = pillow_processor

    def process_doc(self, doc):
        synclog_changes = self._doc_to_changes(doc)
        for change in synclog_changes:
            try:
                self.pillow_processor.process_change(None, change)
            except Exception:
                return False
        return True

    def handle_skip(self, doc):
        print('Unable to process user {}'.format(
            doc['_id'],
        ))
        return True

    def _doc_to_changes(self, doc):
        # creates a change object for the last 10 synclogs
        # of the given user, for the synclog pillow to process.
        # this means we wont have to iterate through all synclogs
        # when reindexing.
        synclogs = get_synclogs_for_user(doc['_id'], limit=10)
        changes = [Change(
            id=res['doc']['_id'],
            sequence_id=None,
            document=res['doc']
        ) for res in synclogs]
        return changes


class UserSyncHistoryReindexer(Reindexer):

    def __init__(self, doc_provider, chunk_size=1000, reset=False):
        self.reset = reset
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = UserSyncHistoryReindexerDocProcessor(UserSyncHistoryProcessor())

    def reindex(self):
        processor = DocumentProcessorController(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )
        processor.run()


class UpdateUserSyncHistoryReindexerFactory(ReindexerFactory):
    slug = 'user-sync-history'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
    ]

    def build(self):
        iteration_key = "UpdateUserSyncHistoryPillow_reindexer"
        doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
            CommCareUser,
            WebUser
        ])
        return UserSyncHistoryReindexer(doc_provider, **self.options)
