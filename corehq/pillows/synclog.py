from corehq.apps.receiverwrapper.util import get_version_and_app_from_build_id
from corehq.apps.users.models import LastSync, CouchUser, CommCareUser, WebUser
from corehq.pillows.utils import update_latest_builds, filter_by_app
from corehq.util.doc_processor.interface import BaseDocProcessor, DocumentProcessorController
from corehq.util.doc_processor.couch import CouchDocumentProvider

from dimagi.utils.parsing import string_to_utc_datetime

from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.interface import PillowProcessor
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.feed.interface import Change
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.reindexer.reindexer import Reindexer

from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_synclogs_for_user


def get_user_sync_history_pillow(pillow_id='UpdateUserSyncHistoryPillow', **kwargs):
    """
    This gets a pillow which iterates through all synclogs
    """
    couch_db = SyncLog.get_db()
    change_feed = CouchChangeFeed(couch_db, include_docs=True)
    checkpoint = PillowCheckpoint('synclog', change_feed.sequence_format)
    form_processor = UserSyncHistoryProcessor()
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100
        ),
    )


def _last_sync_needs_update(last_sync, sync_datetime):
    if not (last_sync and last_sync.sync_date):
        return True
    if sync_datetime > last_sync.sync_date:
        return True
    return False


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

            last_sync = filter_by_app(user.reporting_metadata.last_syncs, app_id)

            if _last_sync_needs_update(last_sync, sync_date):
                if last_sync is None:
                    last_sync = LastSync()
                    user.reporting_metadata.last_syncs.append(last_sync)
                last_sync.sync_date = sync_date
                last_sync.build_version = version
                last_sync.app_id = app_id

                if _last_sync_needs_update(user.reporting_metadata.last_sync_for_user, sync_date):
                    user.reporting_metadata.last_sync_for_user = last_sync

                if version:
                    update_latest_builds(user, app_id, sync_date, version)

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

    def __init__(self, doc_provider, chunk_size=1000):
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = UserSyncHistoryReindexerDocProcessor(UserSyncHistoryProcessor())

    def consume_options(self, options):
        self.reset = options.pop("reset", False)
        self.chunk_size = options.pop("chunksize", self.chunk_size)
        return options

    def reindex(self):
        processor = DocumentProcessorController(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )
        processor.run()


def get_user_sync_history_reindexer():
    iteration_key = "UpdateUserSyncHistoryPillow_reindexer"
    doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
        CommCareUser,
        WebUser
    ])
    return UserSyncHistoryReindexer(doc_provider)
