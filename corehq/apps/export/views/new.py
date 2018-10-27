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
from corehq.apps.export.views.utils import DailySavedExportMixin, DailySavedExportMixin
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
