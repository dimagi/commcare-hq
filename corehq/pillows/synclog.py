from django.conf import settings

from casexml.apps.phone.models import SyncLogSQL
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
from corehq.apps.receiverwrapper.util import get_version_and_app_from_build_id
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

SYNCLOG_SQL_USER_SYNC_GROUP_ID = "synclog_sql_user_sync"


def get_user_sync_history_pillow(
        pillow_id='UpdateUserSyncHistoryPillow', num_processes=1, process_num=0, **kwargs):
    """
    This gets a pillow which iterates through all synclogs
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

        if settings.USER_REPORTING_METADATA_BATCH_ENABLED:
            UserReportingMetadataStaging.add_sync(domain, user_id, app_id, build_id, sync_date, device_id)
        else:
            mark_last_synclog(domain, user_id, build_id, sync_date, device_id)


def mark_last_synclog(domain, user_id, build_id, sync_date, device_id):
    user = CouchUser.get_by_user_id(user_id)
    if not user:
        return

    version, app_id = None, None
    if build_id:
        version, app_id = get_version_and_app_from_build_id(domain, build_id)

    save = update_last_sync(user, app_id, sync_date, version)
    if version:
        save |= update_latest_builds(user, app_id, sync_date, version)

    app_meta = None
    device_id = device_id
    if device_id:
        if app_id:
            app_meta = DeviceAppMeta(app_id=app_id, build_id=build_id, last_sync=sync_date)
        save |= update_device_meta(user, device_id, device_app_meta=app_meta, save=False)

    if save:
        user.save(fire_signals=False)


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
