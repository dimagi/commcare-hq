from datetime import datetime, timedelta

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import View

import pytz
from memoized import memoized

from dimagi.utils.web import get_url_base, json_response
from soil import DownloadBase
from soil.progress import get_task_status

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.decorators import (
    LoginAndDomainMixin,
    api_auth,
    login_and_domain_required,
)
from corehq.apps.export.const import (
    CASE_EXPORT,
    FORM_EXPORT,
    MAX_DATA_FILE_SIZE,
    MAX_DATA_FILE_SIZE_TOTAL,
    BULK_CASE_EXPORT_CACHE,
    MAX_CASE_TYPE_COUNT,
    MAX_APP_COUNT,
    ALL_CASE_TYPE_EXPORT
)
from corehq.apps.export.models import (
    CaseExportDataSchema,
    FormExportDataSchema,
)
from corehq.apps.export.models.new import DataFile, DatePeriod, CaseExportInstance
from corehq.apps.export.tasks import generate_schema_for_all_builds, process_populate_export_tables
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.permissions import (
    CASE_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
    ODATA_FEED_PERMISSION,
    can_download_data_files,
    can_upload_data_files,
    has_permission_to_view_report,
)
from corehq.blobs.exceptions import NotFound
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.util.download import get_download_response
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.app_manager.dbaccessors import get_app_ids_in_domain


def get_timezone(domain, couch_user):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


def user_can_view_deid_exports(domain, couch_user):
    return (domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA)
            and has_permission_to_view_report(couch_user, domain, DEID_EXPORT_PERMISSION))


def user_can_view_odata_feed(domain, couch_user):
    domain_can_view_odata = domain_has_privilege(domain, privileges.ODATA_FEED)
    return (domain_can_view_odata
            and has_permission_to_view_report(couch_user, domain, ODATA_FEED_PERMISSION))


class ExportsPermissionsManager(object):
    """
    Encapsulates some shortcuts for checking export permissions.

    Users need to have edit permissions to create or update exports
    Users need the "view reports" permission to download exports
    The DEIDENTIFIED_DATA privilege is a pro-plan feature, and without it,
        users should not be able to create, update, or download deid exports.
    There are some users with access to a specific DeidExportReport.  If these
        users do not have the "view reports" permission, they should only be
        able to access deid reports.
    """

    def __init__(self, form_or_case, domain, couch_user):
        super(ExportsPermissionsManager, self).__init__()
        if form_or_case and form_or_case not in ['form', 'case']:
            raise ValueError("Unrecognized value for form_or_case")
        self.form_or_case = form_or_case
        self.domain = domain
        self.couch_user = couch_user

    @property
    def has_edit_permissions(self):
        return self.couch_user.can_edit_data()

    @property
    def has_form_export_permissions(self):
        return has_permission_to_view_report(self.couch_user, self.domain, FORM_EXPORT_PERMISSION)

    @property
    def has_case_export_permissions(self):
        return has_permission_to_view_report(self.couch_user, self.domain, CASE_EXPORT_PERMISSION)

    @property
    def has_view_permissions(self):
        if not self.form_or_case:
            return self.has_form_export_permissions or self.has_case_export_permissions
        elif self.form_or_case == "form":
            return self.has_form_export_permissions
        elif self.form_or_case == "case":
            return self.has_case_export_permissions
        return False

    @property
    def has_deid_view_permissions(self):
        # just a convenience wrapper around user_can_view_deid_exports
        return user_can_view_deid_exports(self.domain, self.couch_user)

    @property
    def has_odata_permissions(self):
        return user_can_view_odata_feed(self.domain, self.couch_user)

    def access_list_exports_or_404(self, is_deid=False, is_odata=False):
        if not (self.has_view_permissions
                or (is_deid and self.has_deid_view_permissions)
                or (is_odata and self.has_odata_permissions)):
            raise Http404()

    def access_download_export_or_404(self):
        if not (self.has_view_permissions or self.has_deid_view_permissions):
            raise Http404()


class DailySavedExportMixin(object):

    def _priv_check(self):
        if not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT):
            raise Http404

    def dispatch(self, *args, **kwargs):
        self._priv_check()
        return super().dispatch(*args, **kwargs)

    def create_new_export_instance(self, schema, username, export_settings=None):
        instance = super().create_new_export_instance(
            schema,
            username,
            export_settings=export_settings
        )
        instance.is_daily_saved_export = True

        span = datespan_from_beginning(self.domain_object, get_timezone(self.domain, self.request.couch_user))
        instance.filters.date_period = DatePeriod(
            period_type="since", begin=span.startdate.date()
        )
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        instance.filters.can_access_all_locations = self.request.can_access_all_locations
        instance.filters.accessible_location_ids = accessible_location_ids

        return instance

    @property
    def report_class(self):
        from corehq.apps.export.views.list import DailySavedExportListView
        return DailySavedExportListView


class DashboardFeedMixin(DailySavedExportMixin):

    def _priv_check(self):
        if not domain_has_privilege(self.domain, EXCEL_DASHBOARD):
            raise Http404

    def create_new_export_instance(self, schema, username, export_settings=None):
        instance = super().create_new_export_instance(
            schema,
            username,
            export_settings=export_settings
        )
        instance.export_format = "html"
        return instance

    @property
    def page_context(self):
        context = super().page_context
        context['format_options'] = ["html"]
        return context

    @property
    def report_class(self):
        from corehq.apps.export.views.list import DashboardFeedListView
        return DashboardFeedListView


class ODataFeedMixin(object):

    @method_decorator(requires_privilege_with_fallback(privileges.ODATA_FEED))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @property
    def terminology(self):
        return {
            'page_header': _("OData Feed Settings"),
            'help_text': "",
            'name_label': _("OData Feed Name"),
            'choose_fields_label': _("Choose the fields you want to include in this feed."),
            'choose_fields_description': _("""
                You can drag and drop fields to reorder them. You can also rename
                fields, which will update the field labels in the Power BI/Tableau
            """),
        }

    def create_new_export_instance(self, schema, username, export_settings=None):
        instance = super().create_new_export_instance(
            schema,
            username,
            export_settings=export_settings)
        instance.is_odata_config = True
        instance.transform_dates = False
        return instance

    @property
    def page_context(self):
        context = super().page_context
        context['format_options'] = ["odata"]
        return context

    @property
    @memoized
    def new_export_instance(self):
        export_instance = self.export_instance_cls.get(self.export_id)
        export_instance._id = None
        export_instance._rev = None
        return export_instance

    @property
    def report_class(self):
        from corehq.apps.export.views.list import ODataFeedListView
        return ODataFeedListView

    def get_export_instance(self, schema, original_export_instance):
        export_instance = super().get_export_instance(schema, original_export_instance)
        clean_odata_columns(export_instance)
        export_instance.is_odata_config = True
        export_instance.transform_dates = False
        export_instance.name = _("Copy of {}").format(export_instance.name)
        return export_instance


class GenerateSchemaFromAllBuildsView(LoginAndDomainMixin, View):
    urlname = 'build_full_schema'

    @staticmethod
    def export_cls(export_type):
        return CaseExportDataSchema if export_type == CASE_EXPORT else FormExportDataSchema

    def get(self, request, *args, **kwargs):
        download_id = request.GET.get('download_id')
        download = DownloadBase.get(download_id)
        if download is None:
            return json_response({
                'download_id': download_id,
                'progress': None,
            })

        status = get_task_status(download.task)
        return json_response({
            'download_id': download_id,
            'success': status.success(),
            'failed': status.failed(),
            'missing': status.missing(),
            'not_started': status.not_started(),
            'progress': status.progress._asdict(),
        })

    def post(self, request, *args, **kwargs):
        export_type = request.POST.get('type')
        assert export_type in [CASE_EXPORT, FORM_EXPORT], 'Unrecogized export type {}'.format(export_type)
        download = DownloadBase()
        download.set_task(generate_schema_for_all_builds.delay(
            export_type,
            request.domain,
            request.POST.get('app_id'),
            request.POST.get('identifier'),
        ))
        download.save()
        return json_response({
            'download_id': download.download_id
        })


class DailySavedExportPaywall(BaseProjectDataView):
    urlname = 'daily_saved_paywall'
    template_name = 'export/paywall.html'


class DashboardFeedPaywall(BaseProjectDataView):
    urlname = 'dashboard_feeds_paywall'
    template_name = 'export/paywall.html'


@location_safe
@method_decorator(login_and_domain_required, name='dispatch')
class DataFileDownloadList(BaseProjectDataView):
    urlname = 'download_data_files'
    template_name = 'export/download_data_files.html'
    page_title = gettext_lazy("Secure File Transfer")

    def dispatch(self, request, *args, **kwargs):
        if can_download_data_files(self.domain, request.couch_user):
            return super(DataFileDownloadList, self).dispatch(request, *args, **kwargs)
        else:
            raise Http404

    def get_context_data(self, **kwargs):
        context = super(DataFileDownloadList, self).get_context_data(**kwargs)
        context.update({
            'timezone': get_timezone_for_user(self.request.couch_user, self.domain),
            'data_files': DataFile.get_all(self.domain),
            'is_admin': can_upload_data_files(self.domain, self.request.couch_user),
            'url_base': get_url_base(),
        })
        return context

    def post(self, request, *args, **kwargs):
        if request.FILES['file'].size > MAX_DATA_FILE_SIZE:
            messages.warning(
                request,
                _('The data file exceeds the maximum size of {} MB.').format(MAX_DATA_FILE_SIZE // (1024 * 1024))
            )
            return self.get(request, *args, **kwargs)

        total_size = DataFile.get_total_size(self.domain)
        if total_size and total_size + request.FILES['file'].size > MAX_DATA_FILE_SIZE_TOTAL:
            messages.warning(
                request,
                _('Uploading this data file would exceed the total allowance of {} GB for this project space. '
                  'Please remove some files in order to upload new files.').format(
                    MAX_DATA_FILE_SIZE_TOTAL // (1024 * 1024 * 1024))
            )
            return self.get(request, *args, **kwargs)

        data_file = DataFile.save_blob(
            request.FILES['file'],
            domain=self.domain,
            filename=request.FILES['file'].name,
            description=request.POST['description'],
            content_type=request.FILES['file'].content_type,
            delete_after=datetime.utcnow() + timedelta(hours=int(request.POST['ttl'])),
        )
        messages.success(request, _('Data file "{}" uploaded'.format(data_file.description)))
        return HttpResponseRedirect(reverse(self.urlname, kwargs={'domain': self.domain}))


@method_decorator(api_auth(), name='dispatch')
class DataFileDownloadDetail(BaseProjectDataView):
    urlname = 'download_data_file'

    def dispatch(self, request, *args, **kwargs):
        if can_download_data_files(self.domain, request.couch_user):
            return super(DataFileDownloadDetail, self).dispatch(request, *args, **kwargs)
        else:
            raise Http404

    def get(self, request, *args, **kwargs):
        try:
            data_file = DataFile.get(self.domain, kwargs['pk'])
            blob = data_file.get_blob()
        except (DataFile.DoesNotExist, NotFound):
            raise Http404

        return get_download_response(
            blob, data_file.content_length, data_file.content_type, True, data_file.filename, request
        )

    def delete(self, request, *args, **kwargs):
        try:
            data_file = DataFile.get(self.domain, kwargs['pk'])
        except DataFile.DoesNotExist:
            raise Http404
        data_file.delete()
        return HttpResponse(status=204)


def can_view_form_exports(couch_user, domain):
    return ExportsPermissionsManager('form', domain, couch_user).has_form_export_permissions


def can_view_case_exports(couch_user, domain):
    return ExportsPermissionsManager('case', domain, couch_user).has_case_export_permissions


def clean_odata_columns(export_instance):
    for table in export_instance.tables:
        for column in table.columns:
            column.label = column.label.replace('@', '').replace(
                '.', ' ').replace('\n', '').replace('\t', ' ').replace(
                '#', '').replace(',', '')
            # truncate labels for PowerBI and Tableau limits
            if len(column.label) >= 255:
                column.label = column.label[:255]
            if column.label in ['formid'] and column.is_deleted:
                column.label = f"{column.label}_deleted"


def case_type_or_app_limit_exceeded(domain):
    case_type_count = len(get_case_types_for_domain(domain))
    app_count = len(get_app_ids_in_domain(domain))
    return (case_type_count > MAX_CASE_TYPE_COUNT or app_count > MAX_APP_COUNT)


def trigger_update_case_instance_tables_task(domain, export_id):
    progress_id = f'{BULK_CASE_EXPORT_CACHE}:{domain}'
    process_populate_export_tables.delay(export_id, progress_id)


def is_bulk_case_export(export_instance):
    return (
        isinstance(export_instance, CaseExportInstance)
        and export_instance.case_type == ALL_CASE_TYPE_EXPORT
    )
