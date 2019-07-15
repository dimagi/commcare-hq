from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.http import Http404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy

from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.export.const import CASE_EXPORT, FORM_EXPORT
from corehq.apps.export.models import ExportInstance
from corehq.apps.export.views.new import BaseExportView
from corehq.apps.export.views.utils import (
    DailySavedExportMixin,
    DashboardFeedMixin,
    ODataFeedMixin,
    clean_odata_columns,
    remove_row_number_from_export_columns,
)


class BaseEditNewCustomExportView(BaseExportView):

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def new_export_instance(self):
        return self.export_instance_cls.get(self.export_id)

    def get_export_instance(self, schema, original_export_instance):
        return self.export_instance_cls.generate_instance_from_schema(
            schema,
            saved_export=original_export_instance,
            # The export exists - we don't want to automatically select new columns
            auto_select=False,
        )

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.export_id])

    def get(self, request, *args, **kwargs):
        try:
            export_instance = self.new_export_instance
        except ResourceNotFound:
            raise Http404()

        schema = self.get_export_schema(
            self.domain,
            self.request.GET.get('app_id') or getattr(export_instance, 'app_id'),
            export_instance.identifier
        )
        self.export_instance = self.get_export_instance(schema, export_instance)
        for message in self.export_instance.error_messages():
            messages.error(request, message)
        return super(BaseEditNewCustomExportView, self).get(request, *args, **kwargs)

    @method_decorator(login_and_domain_required)
    def post(self, request, *args, **kwargs):
        try:
            new_export_instance = self.new_export_instance
        except ResourceNotFound:
            new_export_instance = None
        if (
            new_export_instance
            and not new_export_instance.can_edit(request.couch_user)
        ):
            raise Http404
        return super(BaseEditNewCustomExportView, self).post(request, *args, **kwargs)


class EditNewCustomFormExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_form'
    page_title = ugettext_lazy("Edit Form Data Export")
    export_type = FORM_EXPORT

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import FormExportListView
        return FormExportListView


class EditNewCustomCaseExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_case'
    page_title = ugettext_lazy("Edit Case Data Export")
    export_type = CASE_EXPORT

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import CaseExportListView
        return CaseExportListView


class EditCaseFeedView(DashboardFeedMixin, EditNewCustomCaseExportView):
    urlname = 'edit_case_feed_export'
    page_title = ugettext_lazy("Edit Case Feed")


class EditFormFeedView(DashboardFeedMixin, EditNewCustomFormExportView):
    urlname = 'edit_form_feed_export'
    page_title = ugettext_lazy("Edit Form Feed")


class EditCaseDailySavedExportView(DailySavedExportMixin, EditNewCustomCaseExportView):
    urlname = 'edit_case_daily_saved_export'


class EditFormDailySavedExportView(DailySavedExportMixin, EditNewCustomFormExportView):
    urlname = 'edit_form_daily_saved_export'


class EditODataCaseFeedView(ODataFeedMixin, EditNewCustomCaseExportView):
    urlname = 'edit_odata_case_feed'
    page_title = ugettext_lazy("Copy OData Feed")

    def get_export_instance(self, schema, original_export_instance):
        export_instance = super(EditODataCaseFeedView, self).get_export_instance(schema, original_export_instance)
        remove_row_number_from_export_columns(export_instance)
        clean_odata_columns(export_instance)
        return export_instance


class EditODataFormFeedView(ODataFeedMixin, EditNewCustomFormExportView):
    urlname = 'edit_odata_form_feed'
    page_title = ugettext_lazy("Copy OData Feed")

    def get_export_instance(self, schema, original_export_instance):
        export_instance = super(EditODataFormFeedView, self).get_export_instance(schema, original_export_instance)
        remove_row_number_from_export_columns(export_instance)
        clean_odata_columns(export_instance)
        return export_instance


class EditExportAttrView(BaseEditNewCustomExportView):
    export_home_url = None

    @property
    @memoized
    def export_type(self):
        return ExportInstance.get(self.export_id).type

    def get(self, request, *args, **kwargs):
        raise Http404

    def commit(self, request):
        raise NotImplementedError


class EditExportNameView(EditExportAttrView):
    urlname = 'edit_export_name'

    def commit(self, request):
        self.new_export_instance.name = request.POST.get('value')
        self.new_export_instance.save()
        return self.new_export_instance.get_id


class EditExportDescription(EditExportAttrView):
    urlname = 'edit_export_description'

    def commit(self, request):
        self.new_export_instance.description = request.POST.get('value')
        self.new_export_instance.save()
        return self.new_export_instance.get_id
