from django.conf import settings
from django.db import DEFAULT_DB_ALIAS

from casexml.apps.phone.models import SyncLogSQL
from corehq.sql_db.util import handle_connection_failure
from dimagi.utils.parsing import string_to_utc_datetime
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.interface import PillowProcessor
from pillowtop.reindexer.reindexer import Reindexer, ReindexerFactory

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import (
    KafkaChangeFeed,
    KafkaCheckpointEventHandler,
)
from corehq.apps.receiverwrapper.util import get_version_from_build_id
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DeviceAppMeta,
    UserReportingMetadataStaging,
    WebUser,
)
from corehq.apps.users.util import (
    update_device_meta,
    update_last_sync,
    update_latest_builds,
)
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.interface import (
    BaseDocProcessor,
    DocumentProcessorController,
)
from settings import SYNCLOGS_SQL_DB_ALIAS

SYNCLOG_SQL_USER_SYNC_GROUP_ID = "synclog_sql_user_sync"


def _synclog_pillow_dbs():
    return {SYNCLOGS_SQL_DB_ALIAS, DEFAULT_DB_ALIAS}


def get_user_sync_history_pillow(
        pillow_id='UpdateUserSyncHistoryPillow', num_processes=1, process_num=0, **kwargs):
    """Synclog pillow

    Processors:
      - :py:func:`corehq.pillows.synclog.UserSyncHistoryProcessor`
    """
    change_feed = KafkaChangeFeed(
        topics=[topics.SYNCLOG_SQL], client_id=SYNCLOG_SQL_USER_SYNC_GROUP_ID,
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
    """Updates the user document with reporting metadata when a user syncs

    Note when USER_REPORTING_METADATA_BATCH_ENABLED is True that this is written to a postgres table.
    Entries in that table are then batched and processed separately.

    Reads from:
      - CouchDB (user)
      - SynclogSQL table

    Writes to:
      - CouchDB (user) (when batch processing disabled) (default)
      - UserReportingMetadataStaging (SQL)  (when batch processing enabled)
    """

    @handle_connection_failure(get_db_aliases=_synclog_pillow_dbs)
    def process_change(self, change):
        synclog = change.get_document()
        if not synclog:
            return

        user_id = synclog.get('user_id')
        domain = synclog.get('domain')

        if not user_id or not domain:
            return

        try:
            sync_date = string_to_utc_datetime(synclog.get('date'))
        except (ValueError, AttributeError):
            return

        build_id = synclog.get('build_id')
        device_id = synclog.get('device_id')
        app_id = synclog.get('app_id')

        # WebApps syncs do not provide the app_id.
        # For those syncs we go ahead and mark the last synclog synchronously.
        if app_id and settings.USER_REPORTING_METADATA_BATCH_ENABLED:
            UserReportingMetadataStaging.add_sync(domain, user_id, app_id, build_id, sync_date, device_id)
        else:
            user = CouchUser.get_by_user_id(user_id)
            if not user:
                return

            device_app_meta = None
            if device_id and app_id:
                device_app_meta = DeviceAppMeta(app_id=app_id, build_id=build_id, last_sync=sync_date)
            mark_last_synclog(domain, user, app_id, build_id, sync_date, sync_date, device_id, device_app_meta)


def mark_last_synclog(domain, user, app_id, build_id, sync_date, latest_build_date, device_id,
                      device_app_meta, commcare_version=None, build_profile_id=None, fcm_token=None,
                      fcm_token_timestamp=None, save_user=True):
    version = None
    if build_id:
        version = get_version_from_build_id(domain, build_id)

    local_save = False
    if sync_date:
        # sync_date could be null if this is called from a heartbeat request
        local_save |= update_last_sync(user, app_id, sync_date, version)
    if version:
        local_save |= update_latest_builds(user, app_id, latest_build_date, version,
                                           build_profile_id=build_profile_id)

    if device_id:
        local_save |= update_device_meta(user, device_id, commcare_version=commcare_version,
                                         device_app_meta=device_app_meta, fcm_token=fcm_token,
                                         fcm_token_timestamp=fcm_token_timestamp, save=False)
    if local_save and save_user:
        user.save(fire_signals=False)
    return local_save


class UserSyncHistoryReindexerDocProcessor(BaseDocProcessor):

    def __init__(self, pillow_processor):
        self.pillow_processor = pillow_processor

    def process_doc(self, doc):
        synclog_changes = self._doc_to_changes(doc)
        for change in synclog_changes:
            try:
                self.pillow_processor.process_change(change)
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
        synclogs = SyncLogSQL.objects.filter(user_id=doc['_id']).order_by('date')[:10]
        changes = [Change(
            id=res.doc['_id'],
            sequence_id=None,
            document=res.doc
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
