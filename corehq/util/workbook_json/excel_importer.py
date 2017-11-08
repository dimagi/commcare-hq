from __future__ import absolute_import
from corehq.util.workbook_json.excel import WorkbookJSONReader
from soil import DownloadBase


class UnknownFileRefException(Exception):
    pass


class ExcelImporter(object):
    """
    Base class for `SingleExcelImporter` and `MultiExcelImporter`.
    This is not meant to be used directly.
    """

    def __init__(self, task, file_ref_id):
        self.task = task
        self.progress = 0
        self.total_rows = 100

        if self.task:
            DownloadBase.set_progress(self.task, 0, 100)

        download_ref = DownloadBase.get(file_ref_id)
        if download_ref is None:
            raise UnknownFileRefException("Could not find file wih ref %s. It may have expired" % file_ref_id)
        self.workbook = WorkbookJSONReader(download_ref.get_filename())

    def mark_complete(self):
        if self.task:
            DownloadBase.set_progress(self.task, 100, 100)

    def add_progress(self, count=1):
        self.progress += count
        if self.task:
            DownloadBase.set_progress(self.task, self.progress, self.total_rows)


class SingleExcelImporter(ExcelImporter):
    """
    Manage importing from an excel file with only one
    worksheet.
    """

    def __init__(self, task, file_ref_id):
        super(SingleExcelImporter, self).__init__(task, file_ref_id)
        self.worksheet = self.workbook.worksheets[0]
        self.total_rows = self.worksheet.worksheet.get_highest_row()


class MultiExcelImporter(ExcelImporter):
    """
    Manage importing from an excel file with multiple
    relevant worksheets.
    """

    def __init__(self, task, file_ref_id):
        super(MultiExcelImporter, self).__init__(task, file_ref_id)
        self.worksheets = self.workbook.worksheets
        self.add_progress(2)  # Show the user we're on it
        total_rows = sum(ws.worksheet.get_highest_row() for ws in self.worksheets)
        # That took a non-negligible amount of time. Give the user some feedback.
        self.add_progress(3)
        self.total_rows = total_rows
