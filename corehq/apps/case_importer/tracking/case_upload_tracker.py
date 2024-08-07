from celery import uuid
from django.db import transaction

from memoized import memoized

from corehq.apps.case_importer.exceptions import ImporterFileNotFound
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
from corehq.apps.case_importer.const import ALL_CASE_TYPE_IMPORT


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

    def get_tempfile(self):
        return transient_file_store.get_tempfile_ref_for_contents(self.upload_id)

    def check_file(self):
        """
        open a spreadsheet download ref just to test there are no errors opening it

        :raise ImporterError subtypes
        """
        tempfile = self.get_tempfile()
        if not tempfile:
            raise ImporterFileNotFound('file not found in cache')
        open_spreadsheet_download_ref(tempfile)

    def get_spreadsheet(self, worksheet_index=0):
        return get_spreadsheet(self.get_tempfile(), worksheet_index)

    def trigger_upload(self, domain, config_list, comment=None, is_bulk=False):
        """
        Save a CaseUploadRecord and trigger a task that runs the upload
        """
        from corehq.apps.case_importer.tasks import bulk_import_async
        original_filename = transient_file_store.get_filename(self.upload_id)
        with open(self.get_tempfile(), 'rb') as f:
            case_upload_file_meta = persistent_file_store.write_file(f, original_filename, domain)

        config_list_json = [c.to_json() for c in config_list]
        task_id = uuid()
        case_type = config_list[0].case_type
        if is_bulk:
            case_type = ALL_CASE_TYPE_IMPORT

        CaseUploadRecord(
            domain=domain,
            comment=comment,
            upload_id=self.upload_id,
            task_id=task_id,
            couch_user_id=config_list[0].couch_user_id,  # Will be the same for all configs in a bulk import,
                                                         # so we can use the first one in the list.
            case_type=case_type,
            upload_file_meta=case_upload_file_meta,
        ).save()

        bulk_import_async.apply_async((config_list_json, domain, self.upload_id), task_id=task_id)

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
