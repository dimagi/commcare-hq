from django.db import models


class ExportFileType(object):
    CSV = "CSV"
    EXCEL_2007_PLUS = "EXCEL_2007_PLUS"
    EXCEL_PRE_2007 = "EXCEL_PRE_2007"
    CHOICES = (
        (CSV, "CSV (zip file)"),
        (EXCEL_2007_PLUS, "Excel 2007+"),
        (EXCEL_PRE_2007, "Excel (older versions)"),
    )


class DefaultExportSettings(models.Model):
    """
    Represents the default settings for data exports
    Currently configured via the Enterprise Settings UI
    """
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

    # OData Forms Exports
    odata_forms_include_duplicates = models.BooleanField(default=False)
    odata_forms_expand_checkbox = models.BooleanField(default=False)
