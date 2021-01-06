from django.db import models
from django.utils.translation import ugettext_lazy

from couchexport.models import Format


class ExportFileType(object):
    CSV = "CSV"
    EXCEL_2007_PLUS = "EXCEL_2007_PLUS"
    EXCEL_PRE_2007 = "EXCEL_PRE_2007"
    CHOICES = (
        (CSV, ugettext_lazy("CSV (zip file)")),
        (EXCEL_2007_PLUS, ugettext_lazy("Excel 2007+")),
        (EXCEL_PRE_2007, ugettext_lazy("Excel (older versions)")),
    )

    @classmethod
    def get_file_format(cls, filetype):
        if filetype == ExportFileType.EXCEL_2007_PLUS:
            return Format.XLS_2007
        elif filetype == ExportFileType.EXCEL_PRE_2007:
            return Format.XLS
        elif filetype == ExportFileType.CSV:
            return Format.CSV
        else:
            raise ValueError(f"{filetype} is not supported for export")


class DefaultExportSettings(models.Model):
    """
    Represents the default settings for data exports linked to a BillingAccount
    Currently configured via the Enterprise Settings UI
    """

    account = models.ForeignKey('accounting.BillingAccount', null=False, on_delete=models.CASCADE)

    # Forms Exports
    forms_filetype = models.CharField(max_length=25, default=ExportFileType.EXCEL_2007_PLUS,
                                      choices=ExportFileType.CHOICES)
    forms_auto_convert = models.BooleanField(default=True)
    forms_auto_format_cells = models.BooleanField(default=False)
    forms_include_duplicates = models.BooleanField(default=False)
    forms_expand_checkbox = models.BooleanField(default=False)

    # Cases Exports
    cases_filetype = models.CharField(max_length=25, default=ExportFileType.EXCEL_2007_PLUS,
                                      choices=ExportFileType.CHOICES)
    cases_auto_convert = models.BooleanField(default=True)

    # OData Exports
    odata_include_duplicates = models.BooleanField(default=False)
    odata_expand_checkbox = models.BooleanField(default=False)
