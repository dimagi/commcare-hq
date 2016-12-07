from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.util import open_spreadsheet_download_ref, get_spreadsheet
from corehq.util.files import file_extention_from_filename
from dimagi.utils.decorators.memoized import memoized
from soil import DownloadBase
from soil.progress import get_task_status
from soil.util import expose_cached_download


class CaseUpload(object):
    _expiry = 1 * 60 * 60

    def __init__(self, upload_id):
        self.upload_id = upload_id

    @classmethod
    def create(cls, file_object, filename):
        file_extension = file_extention_from_filename(filename)
        soil_download = expose_cached_download(
            file_object.read(), expiry=cls._expiry, file_extension=file_extension)
        return cls(soil_download.download_id)

    @classmethod
    def get(cls, upload_id):
        return cls(upload_id)

    @property
    @memoized
    def _soil_download(self):
        return DownloadBase.get(self.upload_id)

    @property
    @memoized
    def _case_upload_record(self):
        return CaseUploadRecord.objects.get(upload_id=self.upload_id)

    def get_filename(self):
        return self._soil_download.get_filename()

    def check_file(self, named_columns):
        """
        open a spreadsheet download ref just to test there are no errors opening it

        :raise ImporterError subtypes
        """
        open_spreadsheet_download_ref(self._soil_download, named_columns)

    def get_spreadsheet(self, named_columns):
        return get_spreadsheet(self.get_filename(), named_columns)

    def trigger_upload(self, domain, config):
        from corehq.apps.case_importer.tasks import bulk_import_async
        task = bulk_import_async.delay(config, domain, self.upload_id)
        CaseUploadRecord(
            domain=domain,
            upload_id=self.upload_id,
            task_id=task.task_id,
            couch_user_id=config.couch_user_id,
            case_type=config.case_type,
        ).save()

    def get_task_status(self):
        return get_task_status(self._case_upload_record.task)
