from __future__ import absolute_import
from django.urls import reverse
from corehq.apps.indicators.admin.couch_indicators import CouchIndicatorAdminInterface
from corehq.apps.indicators.admin.dynamic_indicators import BaseDynamicIndicatorAdminInterface
from corehq.apps.reports.datatables import DataTablesColumn
from mvp.models import (MVPDaysSinceLastTransmission, MVPActiveCasesIndicatorDefinition,
                        MVPChildCasesByAgeIndicatorDefinition)
from mvp.indicator_admin.forms import MVPDaysSinceLastTransmissionForm, MVPActiveCasesForm, MVPChildCasesByAgeForm


class MVPIndicatorAdminMixin(object):

    @property
    def crud_form_update_url(self):
        return "/a/%s/indicators/mvp/form/" % self.domain

    @property
    def bulk_add_url(self):
        return reverse("mvp_indicator_bulk_copy", args=[self.domain, self.document_class.__name__])


class MVPDaysSinceLastTransmissionAdminInterface(MVPIndicatorAdminMixin, BaseDynamicIndicatorAdminInterface):
    name = "Days Since Last Transmission"
    slug = "mvp_days_since"
    document_class = MVPDaysSinceLastTransmission
    form_class = MVPDaysSinceLastTransmissionForm


class MVPActiveCasesAdminInterface(MVPIndicatorAdminMixin, CouchIndicatorAdminInterface):
    name = "Active Cases"
    slug = "mvp_active_cases"
    document_class = MVPActiveCasesIndicatorDefinition
    form_class = MVPActiveCasesForm

    @property
    def headers(self):
        header = super(MVPActiveCasesAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Case Type"), -4)
        return header


class MVPChildCasesByAgeAdminInterface(MVPActiveCasesAdminInterface):
    name = "Child Case Indicators"
    description = "" #todo
    slug = "mvp_child_cases"
    document_class = MVPChildCasesByAgeIndicatorDefinition
    form_class = MVPChildCasesByAgeForm

    @property
    def headers(self):
        header = super(MVPChildCasesByAgeAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Age Restrictions"), -4)
        header.insert_column(DataTablesColumn("Show Active"), -4)
        return header
