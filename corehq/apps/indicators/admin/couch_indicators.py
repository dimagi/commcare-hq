from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
from corehq.apps.indicators.admin.forms import (CouchIndicatorForm, CountUniqueCouchIndicatorForm,
                                                MedianCouchIndicatorForm, SumLastEmittedCouchIndicatorForm)
from corehq.apps.indicators.models import (CouchIndicatorDef, CountUniqueCouchIndicatorDef, MedianCouchIndicatorDef,
                                           SumLastEmittedCouchIndicatorDef)
from corehq.apps.reports.datatables import DataTablesColumn


class CouchIndicatorAdminInterface(BaseIndicatorAdminInterface):
    name = "Simple Indicators"
    description = "desc needed" #todo
    slug = "couch_simple"
    document_class = CouchIndicatorDef
    form_class = CouchIndicatorForm

    @property
    def headers(self):
        header = super(CouchIndicatorAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Title"), -3)
        header.insert_column(DataTablesColumn("Description"), -3)
        header.insert_column(DataTablesColumn("Couch View"), -3)
        header.insert_column(DataTablesColumn("Indicator Key"), -3)
        header.insert_column(DataTablesColumn("Time Shifts"), -3)
        return header


class CountUniqueCouchIndicatorAdminInterface(CouchIndicatorAdminInterface):
    name = "Count Unique Emitted Values"
    description = "" #todo
    slug = "couch_count_unique"
    document_class = CountUniqueCouchIndicatorDef
    form_class = CountUniqueCouchIndicatorForm


class MedianCouchIndicatorAdminInterface(CouchIndicatorAdminInterface):
    name = "Median of Emitted Values"
    description = "" #todo
    slug = "couch_median"
    document_class = MedianCouchIndicatorDef
    form_class = MedianCouchIndicatorForm


class SumLastEmittedCouchIndicatorAdminInterface(CouchIndicatorAdminInterface):
    name = "Sum Last Emitted Unique Values"
    description = "" #todo
    slug = "couch_sum_last_unique"
    document_class = SumLastEmittedCouchIndicatorDef
    form_class = SumLastEmittedCouchIndicatorForm
