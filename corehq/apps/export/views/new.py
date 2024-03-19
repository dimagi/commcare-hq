import json

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import View

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.export.const import (
    CASE_EXPORT,
    FORM_EXPORT,
    SharingOption,
    PROPERTY_TAG_INFO,
    ALL_CASE_TYPE_EXPORT,
    MAX_CASE_TYPE_COUNT,
    MAX_APP_COUNT
)
from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.exceptions import (
    BadExportConfiguration,
    ExportAppException,
    ExportODataDuplicateLabelException,
)
from corehq.apps.export.models import (
    CaseExportDataSchema,
    CaseExportInstance,
    FormExportDataSchema,
    FormExportInstance,
)
from corehq.apps.export.utils import get_default_export_settings_if_available
from corehq.apps.export.views.utils import (
    DailySavedExportMixin,
    DashboardFeedMixin,
    ODataFeedMixin,
    clean_odata_columns,
    trigger_update_case_instance_tables_task,
    is_bulk_case_export,
    case_type_or_app_limit_exceeded
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.models import WebUser
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD, API_ACCESS
from corehq.apps.data_dictionary.models import CaseProperty


class BaseExportView(BaseProjectDataView):
    """Base class for all create and edit export views"""
    template_name = 'export/customize_export_new.html'
    export_type = None
    metric_name = None  # Override
    is_async = True

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
            'help_text': mark_safe(  # nosec: no user input
                _("""
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
        number_of_apps_to_process = 0
        is_all_case_types_export = (
            isinstance(self.export_instance, CaseExportInstance)
            and self._is_bulk_export
        )
        table_count = 0
        if not is_all_case_types_export:
            # Case History table is not a selectable table, so exclude it from count
            table_count = len([t for t in self.export_instance.tables if t.label != 'Case History'])
            schema = self.get_export_schema(
                self.domain,
                self.request.GET.get('app_id') or getattr(self.export_instance, 'app_id'),
                self.export_instance.identifier,
            )
            number_of_apps_to_process = schema.get_number_of_apps_to_process()

        if self.export_instance.owner_id or not self.export_instance._id:
            sharing_options = SharingOption.CHOICES
        else:
            sharing_options = [SharingOption.EDIT_AND_EXPORT]

        allow_deid = has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

        return {
            'export_instance': self.export_instance,
            'export_home_url': self.export_home_url,
            'allow_deid': allow_deid,
            'has_excel_dashboard_access': domain_has_privilege(self.domain, EXCEL_DASHBOARD),
            'has_daily_saved_export_access': domain_has_privilege(self.domain, DAILY_SAVED_EXPORT),
            'has_api_access': domain_has_privilege(self.domain, API_ACCESS),
            'can_edit': self.export_instance.can_edit(self.request.couch_user),
            'has_other_owner': owner_id and owner_id != self.request.couch_user.user_id,
            'owner_name': WebUser.get_by_user_id(owner_id).username if owner_id else None,
            'format_options': self.format_options,
            'number_of_apps_to_process': number_of_apps_to_process,
            'sharing_options': sharing_options,
            'terminology': self.terminology,
            'is_all_case_types_export': is_all_case_types_export,
            'disable_table_checkbox': (table_count < 2),
            'geo_properties': self._possible_geo_properties,
        }

    @property
    def _possible_geo_properties(self):
        if self.export_type == FORM_EXPORT:
            return []

        if self._is_bulk_export:
            return []

        return list(CaseProperty.objects.filter(
            case_type__domain=self.domain,
            case_type__name=self.export_instance.case_type,
            data_type=CaseProperty.DataType.GPS,
        ).values_list('name', flat=True))

    @property
    def format_options(self):
        format_options = ["xls", "xlsx", "csv"]

        should_support_geojson = (
            self.export_type == CASE_EXPORT
            and toggles.SUPPORT_GEO_JSON_EXPORT.enabled(self.domain)
            and not self._is_bulk_export
        )
        if should_support_geojson:
            format_options.append("geojson")

        return format_options

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.page_title,
            'url': self.export_home_url,
        }]

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body.decode('utf-8')))

        if (
            self.domain != export.domain
                or (export.export_format == "html" and not domain_has_privilege(self.domain, EXCEL_DASHBOARD))
                or (export.is_daily_saved_export and not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT))
                or (export.export_format == "geojson" and not toggles.SUPPORT_GEO_JSON_EXPORT.enabled(self.domain))
        ):
            raise BadExportConfiguration()

        if not export._rev:
            # This is a new export

            track_workflow(
                request.user.username,
                f'{self.metric_name} - Created Export',
                properties={'domain': self.domain}
            )

            if domain_has_privilege(request.domain, privileges.EXPORT_OWNERSHIP):
                export.owner_id = request.couch_user.user_id
            if getattr(settings, "ENTERPRISE_MODE"):
                # default auto rebuild to False for enterprise clusters
                # only do this on first save to prevent disabling on every edit
                export.auto_rebuild_enabled = False

        if export.is_odata_config:
            for table_id, table in enumerate(export.tables):
                labels = []
                for column in table.columns:
                    is_reserved_number = (
                        column.label == 'number' and table_id > 0 and table.selected
                    )
                    if ((column.label in ['formid', 'caseid']
                         and PROPERTY_TAG_INFO in column.tags)
                            or is_reserved_number):
                        column.selected = True
                    elif (column.label in ['formid', 'caseid']
                          and PROPERTY_TAG_INFO not in column.tags):
                        # make sure hidden (eg deleted) labels that are
                        # formid/caseid are never selected
                        column.selected = False

                    if column.label not in labels and column.selected:
                        labels.append(column.label)
                    elif column.selected:
                        raise ExportODataDuplicateLabelException(
                            _("Column labels must be unique. "
                              "'{}' appears more than once.").format(column.label)
                        )
            num_nodes = sum([1 for table in export.tables[1:] if table.selected])
            if hasattr(self, 'is_copy') and self.is_copy:
                event_title = "[BI Integration] Clicked Save button for feed copy"
            else:
                event_title = "[BI Integration] Clicked Save button for feed creation"
            track_workflow(request.user.username, event_title, {
                "Feed Type": export.type,
                "Number of additional nodes": num_nodes,
            })

        export.save()
        messages.success(
            request,
            format_html(_("Export <strong>{}</strong> saved."), export.name)
        )
        return export

    def post(self, request, *args, **kwargs):
        try:
            export = self.commit(request)
            if is_bulk_case_export(export):
                trigger_update_case_instance_tables_task(request.domain, export._id)
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
            if request.POST.get("count"):
                return HttpResponse(url)
            return HttpResponseRedirect(url)

    @memoized
    def get_export_schema(self, domain, app_id, identifier):
        return self.export_schema_cls.generate_schema(
            domain,
            app_id,
            identifier,
            only_process_current_builds=True,
        )

    @memoized
    def get_empty_export_schema(self, domain, identifier):
        return self.export_schema_cls.generate_empty_schema(domain, identifier)

    @property
    def _is_bulk_export(self):
        return self.export_instance.case_type == ALL_CASE_TYPE_EXPORT


@location_safe
class CreateNewCustomFormExportView(BaseExportView):
    urlname = 'new_custom_export_form'
    page_title = gettext_lazy("Create Form Data Export")
    export_type = FORM_EXPORT
    metric_name = 'Form Export'

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import FormExportListView
        return FormExportListView

    def create_new_export_instance(self, schema, username, export_settings=None):
        export = self.export_instance_cls.generate_instance_from_schema(schema, export_settings=export_settings)

        track_workflow(username, f'{self.metric_name} - Clicked Add Export Popup', properties={
            'domain': self.domain
        })

        return export

    def get(self, request, *args, **kwargs):
        app_id = request.GET.get('app_id')
        xmlns = request.GET.get('export_tag').strip('"')

        export_settings = get_default_export_settings_if_available(self.domain)
        schema = self.get_export_schema(self.domain, app_id, xmlns)
        self.export_instance = self.create_new_export_instance(
            schema,
            request.user.username,
            export_settings=export_settings)

        return super(CreateNewCustomFormExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCustomCaseExportView(BaseExportView):
    urlname = 'new_custom_export_case'
    page_title = gettext_lazy("Create Case Data Export")
    export_type = CASE_EXPORT
    metric_name = 'Case Export'

    @property
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import CaseExportListView
        return CaseExportListView

    def create_new_export_instance(self, schema, username, export_settings=None):

        load_deprecated = self.request.GET.get('load_deprecated', 'False') == 'True'
        export = self.export_instance_cls.generate_instance_from_schema(
            schema,
            export_settings=export_settings,
            load_deprecated=load_deprecated
        )

        track_workflow(username, f'{self.metric_name} - Clicked Add Export Popup', properties={
            'domain': self.domain
        })

        return export

    def get(self, request, *args, **kwargs):
        case_type = request.GET.get('export_tag').strip('"')

        # First check if project is allowed to do a bulk export and redirect if necessary
        if case_type == ALL_CASE_TYPE_EXPORT and case_type_or_app_limit_exceeded(self.domain):
            messages.error(
                request,
                _(
                    "Cannot do a bulk case export as the project has more than %(max_case_types)s "
                    "case types or %(max_apps)s applications."
                ) % {
                    'max_case_types': MAX_CASE_TYPE_COUNT,
                    'max_apps': MAX_APP_COUNT
                }
            )
            url = self.export_home_url
            return HttpResponseRedirect(url)

        # Don't add group schemas if doing a bulk case export. There may be a lot of case
        # types, so rather handle creating the instance tables in an async task on the instance save.
        schema = None
        if case_type == ALL_CASE_TYPE_EXPORT:
            schema = self.get_empty_export_schema(self.domain, case_type)
        else:
            schema = self.get_export_schema(self.domain, None, case_type)

        export_settings = get_default_export_settings_if_available(self.domain)
        self.export_instance = self.create_new_export_instance(
            schema,
            request.user.username,
            export_settings=export_settings
        )

        return super(CreateNewCustomCaseExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCaseFeedView(DashboardFeedMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_feed_export'
    metric_name = 'Excel Dashboard Case Export'
    page_title = gettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewFormFeedView(DashboardFeedMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_feed_export'
    metric_name = 'Excel Dashboard Form Export'
    page_title = gettext_lazy("Create Dashboard Feed")


@location_safe
class CreateNewDailySavedCaseExport(DailySavedExportMixin, CreateNewCustomCaseExportView):
    urlname = 'new_case_daily_saved_export'
    metric_name = 'Daily Saved Case Export'


@location_safe
class CreateNewDailySavedFormExport(DailySavedExportMixin, CreateNewCustomFormExportView):
    urlname = 'new_form_faily_saved_export'
    metric_name = 'Daily Saved Form Export'


@method_decorator(requires_privilege_with_fallback(privileges.ODATA_FEED), name='dispatch')
class CreateODataCaseFeedView(ODataFeedMixin, CreateNewCustomCaseExportView):
    urlname = 'new_odata_case_feed'
    page_title = gettext_lazy("Create OData Case Feed")
    metric_name = 'PowerBI Case Export'

    def create_new_export_instance(self, schema, username, export_settings=None):
        export_instance = super().create_new_export_instance(
            schema,
            username,
            export_settings=export_settings
        )
        clean_odata_columns(export_instance)
        return export_instance


@method_decorator(requires_privilege_with_fallback(privileges.ODATA_FEED), name='dispatch')
class CreateODataFormFeedView(ODataFeedMixin, CreateNewCustomFormExportView):
    urlname = 'new_odata_form_feed'
    page_title = gettext_lazy("Create OData Form Feed")
    metric_name = 'PowerBI Form Export'

    def create_new_export_instance(self, schema, username, export_settings=None):
        export_instance = super().create_new_export_instance(
            schema,
            username,
            export_settings=export_settings
        )
        # odata settings only apply to form exports
        if export_settings:
            export_instance.split_multiselects = export_settings.odata_expand_checkbox
        clean_odata_columns(export_instance)
        return export_instance


@location_safe
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
        count = request.POST.get("count")
        if count:
            deletelist = json.loads(request.POST.get("deleteList"))
            self.export_type = self.kwargs.get('export_type')
            export = self.export_instance
            export.delete()
            for item in deletelist:
                bulkexport = self.export_instance_cls.get(item["id"])
                bulkexport.delete()

            if self.export_instance.is_odata_config or self.export_instance.export_format == "html":
                delete = "feed"
            else:
                delete = "export"
            if int(count) > 1:
                message = format_html(_("<strong>{}</strong> {}{} were deleted."), count, delete, "s")
            else:
                message = format_html(_("<strong>{}</strong> {}{} was deleted."), count, delete, "")
            messages.success(
                request,
                message
            )
            return export._id
        else:
            self.export_type = self.kwargs.get('export_type')
            export = self.export_instance
            export.delete()
            messages.success(
                request,
                format_html(_("Export <strong>{}</strong> was deleted."), export.name)
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
            if domain_has_privilege(domain, privileges.EXPORT_OWNERSHIP):
                new_export.owner_id = request.couch_user.user_id
                new_export.sharing = SharingOption.PRIVATE
            new_export.save()
            messages.success(
                request,
                format_html(_("Export <strong>{}</strong> created."), new_export.name)
            )
        redirect = request.GET.get('next', reverse('data_interfaces_default', args=[domain]))
        return HttpResponseRedirect(redirect)
