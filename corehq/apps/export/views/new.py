from __future__ import absolute_import
from __future__ import unicode_literals

import json

from couchdbkit import ResourceNotFound
from dimagi.utils.web import json_response
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.generic import View
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.locations.permissions import location_safe
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.models import WebUser
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT

from corehq.apps.export.const import FORM_EXPORT, CASE_EXPORT, SharingOption
from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.exceptions import ExportAppException, BadExportConfiguration
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
)
from corehq.apps.export.views.utils import (
    DailySavedExportMixin,
    DashboardFeedMixin,
    ODataFeedMixin,
    clean_odata_columns,
    remove_row_number_from_export_columns,
)


class BaseExportView(BaseProjectDataView):
    """Base class for all create and edit export views"""
    template_name = 'export/customize_export_new.html'
    export_type = None
    is_async = True
    allow_deid = True

    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseExportView, self).dispatch(request, *args, **kwargs)

    @property
    def export_helper(self):
        raise NotImplementedError("You must implement export_helper!")

    @property
    def export_instance_cls(self):
        return {
            FORM_EXPORT: FormExportInstance,
            CASE_EXPORT: CaseExportInstance,
        }[self.export_type]

    @property
    def export_schema_cls(self):
        return {
            FORM_EXPORT: FormExportDataSchema,
            CASE_EXPORT: CaseExportDataSchema,
        }[self.export_type]

    @property
    def export_home_url(self):
        return reverse(self.report_class.urlname, args=(self.domain,))

    @property
    def terminology(self):
        return {
            'page_header': _("Export Settings"),
            'help_text': mark_safe(_("""
                Learn more about exports on our <a
                href="https://help.commcarehq.org/display/commcarepublic/Data+Export+Overview"
                target="_blank">Help Site</a>.
            """)),
            'name_label': _("Export Name"),
            'choose_fields_label': _("Choose the fields you want to export."),
            'choose_fields_description': _("""
                You can drag and drop fields to reorder them. You can also rename
                fields, which will update the headers in the export file.
            """),
        }

    @property
    def page_context(self):
        owner_id = self.export_instance.owner_id
        schema = self.get_export_schema(
            self.domain,
            self.request.GET.get('app_id') or getattr(self.export_instance, 'app_id'),
            self.export_instance.identifier,
        )
        if self.export_instance.owner_id or not self.export_instance._id:
            sharing_options = SharingOption.CHOICES
        else:
            sharing_options = [SharingOption.EDIT_AND_EXPORT]
        return {
            'export_instance': self.export_instance,
            'export_home_url': self.export_home_url,
            'allow_deid': self.allow_deid and has_privilege(self.request, privileges.DEIDENTIFIED_DATA),
            'has_excel_dashboard_access': domain_has_privilege(self.domain, EXCEL_DASHBOARD),
            'has_daily_saved_export_access': domain_has_privilege(self.domain, DAILY_SAVED_EXPORT),
            'can_edit': self.export_instance.can_edit(self.request.couch_user),
            'has_other_owner': owner_id and owner_id != self.request.couch_user.user_id,
            'owner_name': WebUser.get_by_user_id(owner_id).username if owner_id else None,
            'format_options': ["xls", "xlsx", "csv"],
            'number_of_apps_to_process': schema.get_number_of_apps_to_process(),
            'sharing_options': sharing_options,
            'terminology': self.terminology,
        }

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.page_title,
            'url': self.export_home_url,
        }]

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body.decode('utf-8')))
        if (self.domain != export.domain
                or (export.export_format == "html" and not domain_has_privilege(self.domain, EXCEL_DASHBOARD))
                or (export.is_daily_saved_export and not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT))):
            raise BadExportConfiguration()

        if not export._rev:
            if toggles.EXPORT_OWNERSHIP.enabled(request.domain):
                export.owner_id = request.couch_user.user_id
            if getattr(settings, "ENTERPRISE_MODE"):
                # default auto rebuild to False for enterprise clusters
                # only do this on first save to prevent disabling on every edit
                export.auto_rebuild_enabled = False
        export.save()
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> saved.").format(
                    export.name
                )
            )
        )
        return export._id

    def post(self, request, *args, **kwargs):
        try:
            export_id = self.commit(request)
        except Exception as e:
            if self.is_async:
                return JsonResponse(data={
                    'error': str(e) or type(e).__name__
                }, status=500)
            elif isinstance(e, ExportAppException):
                return HttpResponseRedirect(request.META['HTTP_REFERER'])
            else:
                raise
        else:
            try:
                post_data = json.loads(self.request.body.decode('utf-8'))
                url = self.export_home_url
                # short circuit to check if the submit is from a create or edit feed
                # to redirect it to the list view
                from corehq.apps.export.views.list import DashboardFeedListView, DailySavedExportListView
                if isinstance(self, DashboardFeedMixin):
                    url = reverse(DashboardFeedListView.urlname, args=[self.domain])
                elif post_data['is_daily_saved_export']:
                    url = reverse(DailySavedExportListView.urlname, args=[self.domain])
            except ValueError:
                url = self.export_home_url
            if self.is_async:
                return json_response({
                    'redirect': url,
                })
            return HttpResponseRedirect(url)

    @memoized
    def get_export_schema(self, domain, app_id, identifier):
        return self.export_schema_cls.generate_schema_from_builds(
            domain,
            app_id,
            identifier,
            only_process_current_builds=True,
        )


@location_safe
class CreateNewCustomFormExportView(BaseExportView):
    urlname = 'new_custom_export_form'
    page_title = ugettext_lazy("Create Form Data Export")
    export_type = FORM_EXPORT

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import FormExportListView
        return FormExportListView

    def create_new_export_instance(self, schema):
        return self.export_instance_cls.generate_instance_from_schema(schema)

    def get(self, request, *args, **kwargs):
        app_id = request.GET.get('app_id')
        xmlns = request.GET.get('export_tag').strip('"')

        schema = self.get_export_schema(self.domain, app_id, xmlns)
        self.export_instance = self.create_new_export_instance(schema)

        return super(CreateNewCustomFormExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCustomCaseExportView(BaseExportView):
    urlname = 'new_custom_export_case'
    page_title = ugettext_lazy("Create Case Data Export")
    export_type = CASE_EXPORT

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import CaseExportListView
        return CaseExportListView

    def create_new_export_instance(self, schema):
        return self.export_instance_cls.generate_instance_from_schema(schema)

    def get(self, request, *args, **kwargs):
        case_type = request.GET.get('export_tag').strip('"')

        schema = self.get_export_schema(self.domain, None, case_type)
        self.export_instance = self.create_new_export_instance(schema)

        return super(CreateNewCustomCaseExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCaseFeedView(DashboardFeedMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_feed_export'
    page_title = ugettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewFormFeedView(DashboardFeedMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_feed_export'
    page_title = ugettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewDailySavedCaseExport(DailySavedExportMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_daily_saved_export'


@location_safe
class CreateNewDailySavedFormExport(DailySavedExportMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_faily_saved_export'


@method_decorator(toggles.ODATA.required_decorator(), name='dispatch')
class CreateODataCaseFeedView(ODataFeedMixin, CreateNewCustomCaseExportView):
    urlname = 'new_odata_case_feed'
    page_title = ugettext_lazy("Create OData Case Feed")
    allow_deid = False

    def create_new_export_instance(self, schema):
        export_instance = super(CreateODataCaseFeedView, self).create_new_export_instance(schema)
        remove_row_number_from_export_columns(export_instance)
        clean_odata_columns(export_instance)
        return export_instance


@method_decorator(toggles.ODATA.required_decorator(), name='dispatch')
class CreateODataFormFeedView(ODataFeedMixin, CreateNewCustomFormExportView):
    urlname = 'new_odata_form_feed'
    page_title = ugettext_lazy("Create OData Form Feed")
    allow_deid = False

    def create_new_export_instance(self, schema):
        export_instance = super(CreateODataFormFeedView, self).create_new_export_instance(schema)
        remove_row_number_from_export_columns(export_instance)
        clean_odata_columns(export_instance)
        return export_instance


class DeleteNewCustomExportView(BaseExportView):
    urlname = 'delete_new_custom_export'
    http_method_names = ['post']
    is_async = False

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def export_instance(self):
        try:
            return self.export_instance_cls.get(self.export_id)
        except ResourceNotFound:
            raise Http404()

    def commit(self, request):
        self.export_type = self.kwargs.get('export_type')
        export = self.export_instance
        export.delete()
        messages.success(
            request,
            mark_safe(
                _("Export <strong>{}</strong> was deleted.").format(
                    export.name
                )
            )
        )
        return export._id

    @property
    @memoized
    def report_class(self):
        # The user will be redirected to the view class returned by this function after a successful deletion
        from corehq.apps.export.views.list import (
            CaseExportListView,
            FormExportListView,
            DashboardFeedListView,
            DailySavedExportListView,
            ODataFeedListView,
        )
        if self.export_instance.is_odata_config:
            return ODataFeedListView
        elif self.export_instance.is_daily_saved_export:
            if self.export_instance.export_format == "html":
                return DashboardFeedListView
            return DailySavedExportListView
        elif self.export_instance.type == FORM_EXPORT:
            return FormExportListView
        elif self.export_instance.type == CASE_EXPORT:
            return CaseExportListView
        else:
            raise Exception("Export does not match any export list views!")


class CopyExportView(View):
    urlname = 'copy_export'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.can_edit_data():
            raise Http404
        else:
            return super(CopyExportView, self).dispatch(request, *args, **kwargs)

    def get(self, request, domain, export_id, *args, **kwargs):
        try:
            export = get_properly_wrapped_export_instance(export_id)
        except ResourceNotFound:
            messages.error(request, _('You can only copy new exports.'))
        else:
            new_export = export.copy_export()
            if toggles.EXPORT_OWNERSHIP.enabled(domain):
                new_export.owner_id = request.couch_user.user_id
                new_export.sharing = SharingOption.PRIVATE
            new_export.save()
            messages.success(
                request,
                mark_safe(
                    _("Export <strong>{}</strong> created.").format(
                        new_export.name
                    )
                )
            )
        redirect = request.GET.get('next', reverse('data_interfaces_default', args=[domain]))
        return HttpResponseRedirect(redirect)
