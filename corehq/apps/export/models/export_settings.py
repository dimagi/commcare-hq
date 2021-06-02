from django.db import models
from django.utils.translation import ugettext_lazy

from couchexport.models import Format


class ExportFileType(object):
    CSV = Format.CSV
    EXCEL_2007_PLUS = Format.XLS_2007
    EXCEL_PRE_2007 = Format.XLS
    CHOICES = (
        (CSV, ugettext_lazy("CSV (zip file)")),
        (EXCEL_2007_PLUS, ugettext_lazy("Excel 2007+")),
        (EXCEL_PRE_2007, ugettext_lazy("Excel (older versions)")),
    )


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
    forms_expand_checkbox = models.BooleanField(default=False)

    # Cases Exports
    cases_filetype = models.CharField(max_length=25, default=ExportFileType.EXCEL_2007_PLUS,
                                      choices=ExportFileType.CHOICES)
    cases_auto_convert = models.BooleanField(default=True)

    # OData Exports
    odata_expand_checkbox = models.BooleanField(default=False)

    def as_dict(self):
        return {
            "forms_filetype": self.forms_filetype,
            "forms_auto_convert": self.forms_auto_convert,
            "forms_auto_format_cells": self.forms_auto_format_cells,
            "forms_expand_checkbox": self.forms_expand_checkbox,
            "cases_filetype": self.cases_filetype,
            "cases_auto_convert": self.cases_auto_convert,
            "odata_expand_checkbox": self.odata_expand_checkbox
        }
