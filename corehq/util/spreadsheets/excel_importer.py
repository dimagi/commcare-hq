from corehq.util.spreadsheets.excel import WorkbookJSONReader
from soil import DownloadBase


class ExcelImporter(object):
    """
    Base class for `SingleExcelImporter` and `MultiExcelImporter`.
    This is not meant to be used directly.
    """

    def __init__(self, task, file_ref_id):
        self.task = task
        self.progress = 0

        if self.task:
            DownloadBase.set_progress(self.task, 0, 100)

        download_ref = DownloadBase.get(file_ref_id)
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
        self.total_rows = sum(ws.worksheet.get_highest_row() for ws in self.worksheets)
