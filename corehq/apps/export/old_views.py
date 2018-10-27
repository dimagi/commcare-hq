from __future__ import absolute_import

from __future__ import division
from __future__ import unicode_literals
from datetime import datetime, date, timedelta

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404, HttpResponse, \
    HttpResponseServerError
from django.template.defaultfilters import filesizeformat
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from corehq.apps.analytics.tasks import send_hubspot_form, HUBSPOT_DOWNLOADED_EXPORT_FORM_ID
from corehq.blobs.exceptions import NotFound
from corehq.util.download import get_download_response
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.toggles import MESSAGE_LOG_METADATA, PAGINATED_EXPORTS
from corehq.apps.export.export import get_export_download, get_export_size
from corehq.apps.export.models.new import DatePeriod, DataFile, EmailExportWhenDoneRequest
from corehq.apps.export.views.util import DailySavedExportMixin, DailySavedExportMixin
from corehq.apps.hqwebapp.views import HQJSONResponseMixin
from corehq.apps.hqwebapp.utils import format_angular_error, format_angular_success
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, location_restricted_response
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter, SubmitHistoryFilter
from corehq.apps.reports.views import should_update_export
from corehq.apps.reports.models import HQUserType
from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT
from django_prbac.utils import has_privilege
from django.utils.decorators import method_decorator
import json
import re
from django.utils.safestring import mark_safe
from django.views.generic import View

from couchexport.writers import XlsLengthException

from djangular.views.mixins import allow_remote_invocation
import pytz
from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.fields import ApplicationDataRMIHelper
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.domain.decorators import login_and_domain_required, api_auth
from corehq.apps.export.tasks import (
    generate_schema_for_all_builds,
    get_saved_export_task_status,
    rebuild_saved_export,
)
from corehq.apps.export.exceptions import (
    ExportAppException,
    BadExportConfiguration,
    ExportFormValidationException,
    ExportAsyncException,
)
from corehq.apps.export.forms import (
    EmwfFilterFormExport,
    FilterCaseESExportDownloadForm,
    FilterSmsESExportDownloadForm,
    CreateExportTagForm,
    DashboardFeedFilterForm,
)
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    SMSExportDataSchema,
    FormExportInstance,
    CaseExportInstance,
    SMSExportInstance,
    ExportInstance,
)
from corehq.apps.export.const import (
    FORM_EXPORT,
    CASE_EXPORT,
    MAX_EXPORTABLE_ROWS,
    MAX_DATA_FILE_SIZE,
    MAX_DATA_FILE_SIZE_TOTAL,
    SharingOption,
    UNKNOWN_EXPORT_OWNER,
)
from corehq.apps.export.dbaccessors import (
    get_form_export_instances,
    get_properly_wrapped_export_instance,
    get_case_exports_by_domain,
    get_form_exports_by_domain,
)
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.hqwebapp.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_ko_validation,
    use_angular_js)
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.models import Permissions, CouchUser, WebUser
from corehq.apps.users.permissions import (
    can_download_data_files,
    CASE_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
    has_permission_to_view_report,
)
from corehq.apps.analytics.tasks import track_workflow
from corehq.util.timezones.utils import get_timezone_for_user
from couchexport.models import Format
from memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response, get_url_base
from dimagi.utils.couch import CriticalSection
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, process_email_request
from soil.progress import get_task_status
from six.moves import map


def _get_timezone(domain, couch_user):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


def user_can_view_deid_exports(domain, couch_user):
    return (domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA)
            and couch_user.has_permission(
                domain,
                get_permission_name(Permissions.view_report),
                data=DEID_EXPORT_PERMISSION
            ))


@location_safe
class DataFileDownloadList(BaseProjectDataView):
    urlname = 'download_data_files'
    template_name = 'export/download_data_files.html'
    page_title = ugettext_lazy("Download Data Files")

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
            'is_admin': self.request.couch_user.is_domain_admin(self.domain),
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


@method_decorator(api_auth, name='dispatch')
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

        format = Format('', data_file.content_type, '', True)
        return get_download_response(
            blob, data_file.content_length, format, data_file.filename, request
        )

    def delete(self, request, *args, **kwargs):
        try:
            data_file = DataFile.get(self.domain, kwargs['pk'])
        except DataFile.DoesNotExist:
            raise Http404
        data_file.delete()
        return HttpResponse(status=204)


class DailySavedExportPaywall(BaseProjectDataView):
    urlname = 'daily_saved_paywall'
    template_name = 'export/paywall.html'


class DashboardFeedPaywall(BaseProjectDataView):
    urlname = 'dashbaord_feeds_paywall'
    template_name = 'export/paywall.html'


class BaseNewExportView(BaseProjectDataView):
    template_name = 'export/customize_export_new.html'
    export_type = None
    is_async = True

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(BaseNewExportView, self).dispatch(request, *args, **kwargs)

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
    @memoized
    def report_class(self):
        from corehq.apps.export.views.list import CaseExportListView, FormExportListView
        try:
            base_views = {
                'form': FormExportListView,
                'case': CaseExportListView,
            }
            return base_views[self.export_type]
        except KeyError:
            raise SuspiciousOperation('Attempted to access list view {}'.format(self.export_type))

    @property
    def page_context(self):
        return {
            'export_instance': self.export_instance,
            'export_home_url': self.export_home_url,
            'allow_deid': has_privilege(self.request, privileges.DEIDENTIFIED_DATA),
            'has_excel_dashboard_access': domain_has_privilege(self.domain, EXCEL_DASHBOARD),
            'has_daily_saved_export_access': domain_has_privilege(self.domain, DAILY_SAVED_EXPORT),
            'can_edit': self.export_instance.can_edit(self.request.couch_user),
        }

    @property
    def parent_pages(self):
        return [{
            'title': self.report_class.page_title,
            'url': self.export_home_url,
        }]

    def commit(self, request):
        export = self.export_instance_cls.wrap(json.loads(request.body))
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
                # todo: this can probably be removed as soon as
                # http://manage.dimagi.com/default.asp?157713 is resolved
                notify_exception(request, 'problem saving an export! {}'.format(str(e)))
                response = json_response({
                    'error': str(e) or type(e).__name__
                })
                response.status_code = 500
                return response
            elif isinstance(e, ExportAppException):
                return HttpResponseRedirect(request.META['HTTP_REFERER'])
            else:
                raise
        else:
            try:
                post_data = json.loads(self.request.body)
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


class BaseModifyNewCustomView(BaseNewExportView):

    @use_ko_validation
    @method_decorator(require_can_edit_data)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseModifyNewCustomView, self).dispatch(request, *args, **kwargs)

    @memoized
    def get_export_schema(self, domain, app_id, identifier):
        return self.export_schema_cls.generate_schema_from_builds(
            domain,
            app_id,
            identifier,
            only_process_current_builds=True,
        )

    @property
    def page_context(self):
        result = super(BaseModifyNewCustomView, self).page_context
        result['format_options'] = ["xls", "xlsx", "csv"]
        if self.export_instance.owner_id:
            result['sharing_options'] = SharingOption.CHOICES
        else:
            result['sharing_options'] = [SharingOption.EDIT_AND_EXPORT]
        schema = self.get_export_schema(
            self.domain,
            self.request.GET.get('app_id') or getattr(self.export_instance, 'app_id'),
            self.export_instance.identifier,
        )
        result['number_of_apps_to_process'] = schema.get_number_of_apps_to_process()
        return result


@location_safe
class CreateNewCustomFormExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_form'
    page_title = ugettext_lazy("Create Form Data Export")
    export_type = FORM_EXPORT

    def create_new_export_instance(self, schema):
        return self.export_instance_cls.generate_instance_from_schema(schema)

    def get(self, request, *args, **kwargs):
        app_id = request.GET.get('app_id')
        xmlns = request.GET.get('export_tag').strip('"')

        schema = self.get_export_schema(self.domain, app_id, xmlns)
        self.export_instance = self.create_new_export_instance(schema)

        return super(CreateNewCustomFormExportView, self).get(request, *args, **kwargs)


@location_safe
class CreateNewCustomCaseExportView(BaseModifyNewCustomView):
    urlname = 'new_custom_export_case'
    page_title = ugettext_lazy("Create Case Data Export")
    export_type = CASE_EXPORT

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


class BaseEditNewCustomExportView(BaseModifyNewCustomView):

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    @memoized
    def new_export_instance(self):
        return self.export_instance_cls.get(self.export_id)

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
        self.export_instance = self.export_instance_cls.generate_instance_from_schema(
            schema,
            saved_export=export_instance,
            # The export exists - we don't want to automatically select new columns
            auto_select=False,
        )
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


class EditNewCustomCaseExportView(BaseEditNewCustomExportView):
    urlname = 'edit_new_custom_export_case'
    page_title = ugettext_lazy("Edit Case Data Export")
    export_type = CASE_EXPORT


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


class DeleteNewCustomExportView(BaseModifyNewCustomView):
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
        )
        if self.export_instance.is_daily_saved_export:
            if self.export_instance.export_format == "html":
                return DashboardFeedListView
            return DailySavedExportListView
        elif self.export_instance.type == FORM_EXPORT:
            return FormExportListView
        elif self.export_instance.type == CASE_EXPORT:
            return CaseExportListView
        else:
            raise Exception("Export does not match any export list views!")


def can_download_daily_saved_export(export, domain, couch_user):
    if (export.is_deidentified
        and user_can_view_deid_exports(domain, couch_user)
    ):
        return True
    elif export.type == FORM_EXPORT and has_permission_to_view_report(
            couch_user, domain, FORM_EXPORT_PERMISSION):
        return True
    elif export.type == CASE_EXPORT and has_permission_to_view_report(
            couch_user, domain, CASE_EXPORT_PERMISSION):
        return True
    return False


@login_and_domain_required
@require_POST
def add_export_email_request(request, domain):
    download_id = request.POST.get('download_id')
    user_id = request.couch_user.user_id
    if download_id is None or user_id is None:
        return HttpResponseBadRequest(ugettext_lazy('Download ID or User ID blank/not provided'))
    try:
        download_context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError(ugettext_lazy('Export failed'))
    if download_context.get('is_ready', False):
        try:
            couch_user = CouchUser.get_by_user_id(user_id, domain=domain)
        except CouchUser.AccountTypeError:
            return HttpResponseBadRequest(ugettext_lazy('Invalid user'))
        if couch_user is not None:
            process_email_request(domain, download_id, couch_user.get_email())
    else:
        EmailExportWhenDoneRequest.objects.create(domain=domain, download_id=download_id, user_id=user_id)
    return HttpResponse(ugettext_lazy('Export e-mail request sent.'))


@location_safe
@csrf_exempt
@api_auth
@require_GET
def download_daily_saved_export(req, domain, export_instance_id):
    with CriticalSection(['export-last-accessed-{}'.format(export_instance_id)]):
        try:
            export_instance = get_properly_wrapped_export_instance(export_instance_id)
        except ResourceNotFound:
            raise Http404(_("Export not found"))

        assert domain == export_instance.domain

        if export_instance.export_format == "html":
            if not domain_has_privilege(domain, EXCEL_DASHBOARD):
                raise Http404
        elif export_instance.is_daily_saved_export:
            if not domain_has_privilege(domain, DAILY_SAVED_EXPORT):
                raise Http404

        if not export_instance.filters.is_location_safe_for_user(req):
            return location_restricted_response(req)

        if not can_download_daily_saved_export(export_instance, domain, req.couch_user):
            raise Http404

        if export_instance.export_format == "html":
            message = "Download Excel Dashboard"
        else:
            message = "Download Saved Export"
        track_workflow(req.couch_user.username, message, properties={
            'domain': domain,
            'is_dimagi': req.couch_user.is_dimagi
        })

        if should_update_export(export_instance.last_accessed):
            try:
                rebuild_saved_export(export_instance_id, manual=False)
            except Exception:
                notify_exception(
                    req,
                    'Failed to rebuild export during download',
                    {
                        'export_instance_id': export_instance_id,
                        'domain': domain,
                    },
                )

        export_instance.last_accessed = datetime.utcnow()
        export_instance.save()

    payload = export_instance.get_payload(stream=True)
    format = Format.from_format(export_instance.export_format)
    return get_download_response(payload, export_instance.file_size, format, export_instance.filename, req)


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
        referer = request.META.get('HTTP_REFERER', reverse('data_interfaces_default', args=[domain]))
        return HttpResponseRedirect(referer)
