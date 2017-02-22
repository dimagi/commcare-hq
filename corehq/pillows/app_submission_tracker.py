from __future__ import print_function
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, MultiTopicCheckpointEventHandler
from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document, \
    change_meta_from_doc_meta_and_document
from corehq.apps.change_feed.data_sources import FORM_SQL, COUCH
from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.interface import BaseDocProcessor, DocumentProcessorController
from corehq.util.doc_processor.sql import SqlDocumentProvider
from couchforms.models import XFormInstance, XFormArchived, XFormError, XFormDeprecated, \
    XFormDuplicate, SubmissionErrorLog
from pillowtop.checkpoints.manager import PillowCheckpoint
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.form import AppFormSubmissionTrackerProcessor
from pillowtop.reindexer.reindexer import Reindexer


def get_app_form_submission_tracker_pillow(pillow_id='AppFormSubmissionTrackerPillow'):
    """
    This gets a pillow which iterates through all forms and marks the corresponding app
    as having submissions. This could be expanded to be more generic and include
    other processing that needs to happen on each form
    """
    checkpoint = PillowCheckpoint('app-form-submission-tracker')
    form_processor = AppFormSubmissionTrackerProcessor()
    change_feed = KafkaChangeFeed(topics=[topics.FORM, topics.FORM_SQL], group_id='form-processsor')
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=MultiTopicCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed,
        ),
    )


class AppFormSubmissionReindexDocProcessor(BaseDocProcessor):
    def __init__(self, pillow_processor, data_source_type, data_source_name):
        self.pillow_processor = pillow_processor
        self.data_source_type = data_source_type
        self.data_source_name = data_source_name

    def process_doc(self, doc):
        change = self._doc_to_change(doc, self.data_source_type, self.data_source_name)
        try:
            self.pillow_processor.process_change(None, change)
        except Exception:
            return False
        else:
            return True

    def handle_skip(self, doc):
        print('Unable to process form {} with build {}'.format(
            doc['_id'],
            doc.get('build_id')
        ))
        return True

    @staticmethod
    def _doc_to_change(doc, data_source_type, data_source_name):
        doc_meta = get_doc_meta_object_from_document(doc)
        change_meta = change_meta_from_doc_meta_and_document(
            doc_meta=doc_meta,
            document=doc,
            data_source_type=data_source_type,
            data_source_name=data_source_name,
        )
        return Change(
            id=change_meta.document_id,
            sequence_id=None,
            document=doc,
            deleted=change_meta.is_deletion,
            metadata=change_meta,
            document_store=None,
        )


class AppFormSubmissionReindexer(Reindexer):
    reset = False

    def __init__(self, doc_provider, data_source_type, data_source_name, chunk_size=1000):
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = AppFormSubmissionReindexDocProcessor(
            AppFormSubmissionTrackerProcessor(),
            data_source_type,
            data_source_name,
        )

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


def get_couch_app_form_submission_tracker_reindexer():
    iteration_key = "CouchAppFormSubmissionTrackerPillow_reindexer"
    doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
        XFormInstance,
        XFormArchived,
        XFormError,
        XFormDeprecated,
        XFormDuplicate,
        ('HQSubmission', XFormInstance),
        SubmissionErrorLog,
    ])
    return AppFormSubmissionReindexer(doc_provider, COUCH, XFormInstance.get_db().dbname)


def get_sql_app_form_submission_tracker_reindexer():
    iteration_key = "SqlAppFormSubmissionTrackerPillow_reindexer"
    doc_provider = SqlDocumentProvider(
        iteration_key,
        FormReindexAccessor(include_attachments=False)
    )
    return AppFormSubmissionReindexer(doc_provider, FORM_SQL, 'form_processor_xforminstancesql')
