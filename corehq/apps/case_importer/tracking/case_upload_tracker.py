import time

from django.db import transaction

from memoized import memoized

from corehq.apps.case_importer.exceptions import ImporterRefError
from corehq.apps.case_importer.tracking.exceptions import TimedOutWaitingForCaseUploadRecord
from corehq.apps.case_importer.tracking.filestorage import (
    persistent_file_store,
    transient_file_store,
)
from corehq.apps.case_importer.tracking.models import (
    CaseUploadFormRecord,
    CaseUploadRecord,
)
from corehq.apps.case_importer.util import (
    get_spreadsheet,
    open_spreadsheet_download_ref,
)


class CaseUpload(object):

    def __init__(self, upload_id):
        self.upload_id = upload_id

    @classmethod
    def create(cls, file_object, filename, domain):
        meta = transient_file_store.write_file(file_object, filename, domain)
        return cls(meta.identifier)

    @classmethod
    def get(cls, upload_id):
        return cls(upload_id)

    @property
    @memoized
    def _case_upload_record(self):
        return CaseUploadRecord.objects.get(upload_id=self.upload_id)

    def wait_for_case_upload_record(self):
        for wait_seconds in [1, 2, 5, 10, 20]:
            try:
                self._case_upload_record
                return
            except CaseUploadRecord.DoesNotExist:
                time.sleep(wait_seconds)
        raise TimedOutWaitingForCaseUploadRecord()

    def get_tempfile(self):
        return transient_file_store.get_tempfile_ref_for_contents(self.upload_id)

    def check_file(self):
        """
        open a spreadsheet download ref just to test there are no errors opening it

        :raise ImporterError subtypes
        """
        tempfile = self.get_tempfile()
        if not tempfile:
            raise ImporterRefError('file not found in cache')
        open_spreadsheet_download_ref(tempfile)

    def get_spreadsheet(self):
        return get_spreadsheet(self.get_tempfile())

    def trigger_upload(self, domain, config, comment=None):
        """
        Save a CaseUploadRecord and trigger a task that runs the upload

        The task triggered by this must call case_upload.wait_for_case_upload_record() before using it
        to avoid a race condition.
        """
        from corehq.apps.case_importer.tasks import bulk_import_async
        original_filename = transient_file_store.get_filename(self.upload_id)
        with open(self.get_tempfile(), 'rb') as f:
            case_upload_file_meta = persistent_file_store.write_file(f, original_filename, domain)

        task = bulk_import_async.delay(config.to_json(), domain, self.upload_id)
        CaseUploadRecord(
            domain=domain,
            comment=comment,
            upload_id=self.upload_id,
            task_id=task.task_id,
            couch_user_id=config.couch_user_id,
            case_type=config.case_type,
            upload_file_meta=case_upload_file_meta,
        ).save()

    def store_task_result(self, task_status):
        self._case_upload_record.save_task_status_json(task_status)

    def store_failed_task_result(self):
        self._case_upload_record.save_task_status_json_if_failed()

    def record_form(self, form_id):
        case_upload_record = self._case_upload_record
        with transaction.atomic():
            form_record = CaseUploadFormRecord(
                case_upload_record=case_upload_record, form_id=form_id)
            form_record.save()
