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
        if form_or_case not in [None, 'form', 'case']:
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
        if self.form_or_case is None:
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

    def access_list_exports_or_404(self, is_deid=False):
        if not (self.has_edit_permissions or self.has_view_permissions
                or (is_deid and self.has_deid_view_permissions)):
            raise Http404()

    def access_download_export_or_404(self):
        if not (self.has_edit_permissions or self.has_view_permissions or self.has_deid_view_permissions):
            raise Http404()


class DailySavedExportMixin(object):

    def _priv_check(self):
        if not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT):
            raise Http404

    def dispatch(self, *args, **kwargs):
        self._priv_check()
        return super(DailySavedExportMixin, self).dispatch(*args, **kwargs)

    def create_new_export_instance(self, schema):
        instance = super(DailySavedExportMixin, self).create_new_export_instance(schema)
        instance.is_daily_saved_export = True

        span = datespan_from_beginning(self.domain_object, _get_timezone(self.domain, self.request.couch_user))
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

    def create_new_export_instance(self, schema):
        instance = super(DashboardFeedMixin, self).create_new_export_instance(schema)
        instance.export_format = "html"
        return instance

    @property
    def page_context(self):
        context = super(DashboardFeedMixin, self).page_context
        context['format_options'] = ["html"]
        return context

    @property
    def report_class(self):
        from corehq.apps.export.views.list import DashboardFeedListView
        return DashboardFeedListView


class GenerateSchemaFromAllBuildsView(View):
    urlname = 'build_full_schema'

    def export_cls(self, type_):
        return CaseExportDataSchema if type_ == CASE_EXPORT else FormExportDataSchema

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
        type_ = request.POST.get('type')
        assert type_ in [CASE_EXPORT, FORM_EXPORT], 'Unrecogized export type {}'.format(type_)
        download = DownloadBase()
        download.set_task(generate_schema_for_all_builds.delay(
            self.export_cls(type_),
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
    urlname = 'dashbaord_feeds_paywall'
    template_name = 'export/paywall.html'


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
