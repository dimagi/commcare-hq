from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document, \
    change_meta_from_doc_meta_and_document
from corehq.apps.change_feed.data_sources import FORM_SQL, COUCH
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.reports.analytics.esaccessors import get_last_forms_by_app
from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.util.doc_processor.couch import CouchDocumentProvider
from corehq.util.doc_processor.interface import BaseDocProcessor, DocumentProcessorController
from corehq.util.doc_processor.sql import SqlDocumentProvider
from couchforms.models import XFormInstance, XFormArchived, XFormError, XFormDeprecated, \
    XFormDuplicate, SubmissionErrorLog
from pillowtop.checkpoints.manager import KafkaPillowCheckpoint
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.form import FormSubmissionMetadataTrackerProcessor
from pillowtop.reindexer.reindexer import Reindexer, ReindexerFactory


def get_form_submission_metadata_tracker_pillow(pillow_id='FormSubmissionMetadataTrackerProcessor',
                                                num_processes=1, process_num=0, **kwargs):
    """
    This gets a pillow which iterates through all forms and marks the corresponding app
    as having submissions. This could be expanded to be more generic and include
    other processing that needs to happen on each form
    """
    change_feed = KafkaChangeFeed(
        topics=topics.FORM_TOPICS, group_id='form-processsor',
        num_processes=num_processes, process_num=process_num
    )
    checkpoint = KafkaPillowCheckpoint('form-submission-metadata-tracker', topics.FORM_TOPICS)
    form_processor = FormSubmissionMetadataTrackerProcessor()
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=form_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
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

    def __init__(self, doc_provider, data_source_type, data_source_name, chunk_size=1000, reset=False):
        self.reset = reset
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = AppFormSubmissionReindexDocProcessor(
            FormSubmissionMetadataTrackerProcessor(),
            data_source_type,
            data_source_name,
        )

    def reindex(self):
        processor = DocumentProcessorController(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )
        processor.run()


class CouchAppFormSubmissionTrackerReindexerFactory(ReindexerFactory):
    slug = 'couch-app-form-submission'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
    ]

    def build(self):
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
        return AppFormSubmissionReindexer(
            doc_provider, COUCH, XFormInstance.get_db().dbname, **self.options
        )


class SqlAppFormSubmissionTrackerReindexerFactory(ReindexerFactory):
    slug = 'sql-app-form-submission'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
    ]

    def build(self):
        iteration_key = "SqlAppFormSubmissionTrackerPillow_reindexer"
        doc_provider = SqlDocumentProvider(
            iteration_key,
            FormReindexAccessor(include_attachments=False)
        )
        return AppFormSubmissionReindexer(
            doc_provider, FORM_SQL, 'form_processor_xforminstancesql', **self.options
        )


class UserAppFormSubmissionDocProcessor(BaseDocProcessor):
    def __init__(self, pillow_processor):
        self.pillow_processor = pillow_processor

    def process_doc(self, doc):
        form_submission_changes = self._doc_to_changes(doc)
        for change in form_submission_changes:
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
        # creates a change object for the last form submission
        # for the user to each of their apps.
        # this allows us to reindex for the app status report
        # without reindexing all forms.
        changes = []
        forms = get_last_forms_by_app(doc['_id'])
        for form in forms:
            doc_meta = get_doc_meta_object_from_document(form)
            change_meta = change_meta_from_doc_meta_and_document(
                doc_meta=doc_meta,
                document=form,
                data_source_type='elasticsearch',
                data_source_name='hqforms',
            )
            changes.append(Change(
                id=change_meta.document_id,
                sequence_id=None,
                document=form,
                deleted=change_meta.is_deletion,
                metadata=change_meta,
                document_store=None,
            ))
        return changes


class UserAppFormSubmissionReindexer(Reindexer):
    def __init__(self, doc_provider, chunk_size=1000, reset=False):
        self.reset = reset
        self.doc_provider = doc_provider
        self.chunk_size = chunk_size
        self.doc_processor = UserAppFormSubmissionDocProcessor(FormSubmissionMetadataTrackerProcessor())

    def reindex(self):
        processor = DocumentProcessorController(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )
        processor.run()


class UserAppFormSubmissionReindexerFactory(ReindexerFactory):
    slug = 'user-app-form-submission'
    arg_contributors = [
        ReindexerFactory.resumable_reindexer_args,
    ]

    def build(self):
        iteration_key = "UserAppFormSubmissionTrackerPillow_reindexer"
        doc_provider = CouchDocumentProvider(iteration_key, doc_type_tuples=[
            CommCareUser,
            WebUser
        ])
        return UserAppFormSubmissionReindexer(doc_provider, **self.options)
