from corehq.apps.receiverwrapper.util import get_version_and_app_from_build_id
from corehq.apps.users.models import LastSync, CouchUser, CommCareUser, WebUser
from corehq.pillows.dbaccessors import get_last_synclogs_for_user
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


def get_synclog_pillow(pillow_id='SynclogPillow'):
    """
    This gets a pillow which iterates through all synclogs
    """
    couch_db = SyncLog.get_db()
    change_feed = CouchChangeFeed(couch_db, include_docs=True)
    checkpoint = PillowCheckpoint('synclog', couch_db)
    form_processor = SynclogProcessor()
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100
        ),
    )


class SynclogProcessor(PillowProcessor):

    def process_change(self, pillow_instance, change):

        synclog = change.get_document()
        if not synclog:
            return

        version = None
        app_id = None
        try:
            last_sync_date = string_to_utc_datetime(synclog.get('date'))
        except ValueError:
            return
        build_id = synclog.get('build_id')
        if build_id:
            version, app_id = get_version_and_app_from_build_id(synclog.get('domain'), build_id)
        user_id = synclog.get('user_id')

        if user_id:
            user = CouchUser.get_by_user_id(user_id)

            last_sync = filter_by_app(user.reporting_metadata.last_syncs, app_id)

            if last_sync is None or last_sync_date >= last_sync.sync_date:
                if last_sync is None:
                    last_sync = LastSync()
                    user.reporting_metadata.last_syncs.append(last_sync)
                last_sync.sync_date = last_sync_date
                last_sync.build_version = version
                last_sync.app_id = app_id

                if user.reporting_metadata.last_sync_for_user is None \
                        or last_sync_date > user.reporting_metadata.last_sync_for_user.sync_date:
                    user.reporting_metadata.last_sync_for_user = last_sync

                if version:
                    update_latest_builds(user, app_id, last_sync_date, version)

                user.save()


class SynclogReindexerDocProcessor(BaseDocProcessor):

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
        synclogs = get_last_synclogs_for_user(doc['_id'])
        changes = [Change(
            id=res['doc']['_id'],
            sequence_id=None,
            document=res['doc']
        ) for res in synclogs]
        return changes


class SynclogReindexer(Reindexer):

    def __init__(self, doc_provider, chunk_size=1000):
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = SynclogReindexerDocProcessor(SynclogProcessor())

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


def get_synclog_reindexer():
    iteration_key = "SynclogPillow_reindexer"
    doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
        CommCareUser,
        WebUser
    ])
    return SynclogReindexer(doc_provider)
