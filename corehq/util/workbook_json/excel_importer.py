import logging
from datetime import datetime, timedelta

from django.conf import settings
from soil import DownloadBase

from corehq.util.workbook_json.excel import WorkbookJSONReader

from .exceptions import UnknownFileRefException


class ExcelImporter(object):
    """
    Base class for `SingleExcelImporter` and `MultiExcelImporter`.
    This is not meant to be used directly.
    """

    def __init__(self, task, file_ref_id):
        self.start = self.last_update = datetime.now()
        self.task = task
        self.progress = 0
        self.total_rows = 100
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            # Log progress since tasks are executed synchronously when
            # CELERY_TASK_ALWAYS_EAGER is true
            self.log = logging.getLogger(__name__).info
        else:
            self.log = lambda *a, **k: None

        if self.task:
            DownloadBase.set_progress(self.task, 0, 100)

        download_ref = DownloadBase.get(file_ref_id)
        if download_ref is None:
            raise UnknownFileRefException("Could not find file wih ref %s. It may have expired" % file_ref_id)
        self.workbook = WorkbookJSONReader(download_ref.get_filename())

    def mark_complete(self):
        if self.task:
            DownloadBase.set_progress(self.task, 100, 100)
        self.log("processed %s / %s in %s",
            self.progress, self.total_rows, datetime.now() - self.start)

    def add_progress(self, count=1):
        self.progress += count
        if self.task:
            DownloadBase.set_progress(self.task, self.progress, self.total_rows)
        if datetime.now() > self.last_update + timedelta(seconds=5):
            self.log("processed %s / %s", self.progress, self.total_rows)
            self.last_update = datetime.now()


class SingleExcelImporter(ExcelImporter):
    """
    Manage importing from an excel file with only one
    worksheet.
    """

    def __init__(self, task, file_ref_id):
        super(SingleExcelImporter, self).__init__(task, file_ref_id)
        self.worksheet = self.workbook.worksheets[0]
        self.total_rows = self.worksheet.worksheet.max_row


class MultiExcelImporter(ExcelImporter):
    """
    Manage importing from an excel file with multiple
    relevant worksheets.
    """

    def __init__(self, task, file_ref_id):
        super(MultiExcelImporter, self).__init__(task, file_ref_id)
        self.worksheets = self.workbook.worksheets
        self.add_progress(2)  # Show the user we're on it
        total_rows = sum(ws.worksheet.max_row for ws in self.worksheets)
        # That took a non-negligible amount of time. Give the user some feedback.
        self.add_progress(3)
        self.total_rows = total_rows
