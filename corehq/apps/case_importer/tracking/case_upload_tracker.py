from corehq.apps.case_importer.exceptions import ImporterRefError
from corehq.apps.case_importer.tracking.filestorage import transient_file_store, \
    persistent_file_store
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.util import open_spreadsheet_download_ref, get_spreadsheet
from dimagi.utils.decorators.memoized import memoized
from soil.progress import get_task_status


class CaseUpload(object):

    def __init__(self, upload_id):
        self.upload_id = upload_id

    @classmethod
    def create(cls, file_object, filename):
        upload_id = transient_file_store.write_file(file_object, filename).identifier
        return cls(upload_id)

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
            raise ImporterRefError('file not found in cache')
        open_spreadsheet_download_ref(tempfile)

    def get_spreadsheet(self):
        return get_spreadsheet(self.get_tempfile())

    def trigger_upload(self, domain, config):
        from corehq.apps.case_importer.tasks import bulk_import_async
        task = bulk_import_async.delay(config, domain, self.upload_id)
        original_filename = transient_file_store.get_filename(self.upload_id)
        with open(self.get_tempfile()) as f:
            case_upload_file_meta = persistent_file_store.write_file(f, original_filename)

        CaseUploadRecord(
            domain=domain,
            upload_id=self.upload_id,
            task_id=task.task_id,
            couch_user_id=config.couch_user_id,
            case_type=config.case_type,
            upload_file_meta=case_upload_file_meta,
        ).save()

    def get_task_status(self):
        return get_task_status(self._case_upload_record.task)
