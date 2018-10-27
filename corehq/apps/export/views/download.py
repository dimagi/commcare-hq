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
from corehq.apps.export.views.util import ExportsPermissionsManager, get_timezone
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


class BaseDownloadExportView(HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/download_export.html'
    http_method_names = ['get', 'post']
    show_date_range = False
    check_for_multimedia = False
    # Form used for rendering filters
    filter_form_class = None
    sms_export = False
    # To serve filters for export from mobile_user_and_group_slugs
    export_filter_class = None
    mobile_user_and_group_slugs_regex = re.compile(
        '(emw=|case_list_filter=|location_restricted_mobile_worker=){1}([^&]*)(&){0,1}'
    )

    @use_daterangepicker
    @use_select2
    @use_angular_js
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        self.permissions = ExportsPermissionsManager(self.form_or_case, request.domain, request.couch_user)
        self.permissions.access_download_export_or_404()

        return super(BaseDownloadExportView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.is_ajax():
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)
        return super(BaseDownloadExportView, self).post(request, *args, **kwargs)

    @property
    @memoized
    def timezone(self):
        return get_timezone(self.domain, self.request.couch_user)

    @property
    @memoized
    def default_datespan(self):
        return datespan_from_beginning(self.domain_object, self.timezone)

    @property
    def page_context(self):
        context = {
            'download_export_form': self.download_export_form,
            'export_list': self.export_list,
            'export_list_url': self.export_list_url,
            'max_column_size': self.max_column_size,
            'show_date_range': self.show_date_range,
            'check_for_multimedia': self.check_for_multimedia,
            'is_sms_export': self.sms_export,
            'user_types': HQUserType.human_readable
        }
        if (
            self.default_datespan.startdate is not None
            and self.default_datespan.enddate is not None
        ):
            context.update({
                'default_date_range': '{startdate}{separator}{enddate}'.format(
                    startdate=self.default_datespan.startdate.strftime('%Y-%m-%d'),
                    enddate=self.default_datespan.enddate.strftime('%Y-%m-%d'),
                    separator=DateRangePickerWidget.separator,
                ),
            })
        else:
            context.update({
                'default_date_range': _(
                    "You have no submissions in this project."
                ),
                'show_no_submissions_warning': True,
            })
        if self.export_filter_class:
            context['dynamic_filters'] = self.export_filter_class(
                self.request, self.request.domain
            ).render()
        return context

    @property
    def export_list_url(self):
        """Should return a the URL for the export list view"""
        raise NotImplementedError("You must implement export_list_url")

    @property
    def download_export_form(self):
        """Should return a memoized instance that is a subclass of
        FilterExportDownloadForm.
        """
        raise NotImplementedError("You must implement download_export_form.")

    @property
    def export_id(self):
        return self.kwargs.get('export_id')

    @property
    def page_url(self):
        if self.export_id:
            return reverse(self.urlname, args=(self.domain, self.export_id))
        return reverse(self.urlname, args=(self.domain,))

    @property
    def export_list(self):
        exports = []
        if (
            self.request.method == 'POST'
            and 'export_list' in self.request.POST
            and not self.request.is_ajax()
        ):
            raw_export_list = json.loads(self.request.POST['export_list'])
            exports = [self._get_export(self.domain, e['id']) for e in raw_export_list]
        elif self.export_id or self.sms_export:
            exports = [self._get_export(self.domain, self.export_id)]

        if not self.permissions.has_view_permissions:
            if self.permissions.has_deid_view_permissions:
                exports = [x for x in exports if x.is_safe]
            else:
                raise Http404()

        # if there are no exports, this page doesn't exist
        if not exports:
            raise Http404()

        exports = [self.download_export_form.format_export_data(e) for e in exports]
        return exports

    def _get_export(self, domain, export_id):
        raise NotImplementedError()

    @property
    def max_column_size(self):
        try:
            return int(self.request.GET.get('max_column_size', 2000))
        except TypeError:
            return 2000

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        raise NotImplementedError("Must return a list of export filter objects")

    @allow_remote_invocation
    def poll_custom_export_download(self, in_data):
        """Polls celery to see how the export download task is going.
        :param in_data: dict passed by the  angular js controller.
        :return: final response: {
            'success': True,
            'dropbox_url': '<url>',
            'download_url: '<url>',
            <task info>
        }
        """
        try:
            download_id = in_data['download_id']
        except KeyError:
            return format_angular_error(_("Requires a download id"), log_error=False)
        try:
            context = get_download_context(download_id)
        except TaskFailedError:
            notify_exception(self.request, "Export download failed",
                             details={'download_id': download_id})
            return format_angular_error(
                _("Download Task Failed to Start. It seems that the server "
                  "might be under maintenance."),
                log_error=False,
            )
        if context.get('is_ready', False):
            context.update({
                'dropbox_url': reverse('dropbox_upload', args=(download_id,)),
                'download_url': "{}?get_file".format(
                    reverse('retrieve_download', args=(download_id,))
                ),
            })
        context['is_poll_successful'] = True
        return context

    def _get_download_task(self, in_data):
        export_filters, export_specs = self._process_filters_and_specs(in_data)
        export_instances = [self._get_export(self.domain, spec['export_id']) for spec in export_specs]
        self._check_deid_permissions(export_instances)
        self._check_export_size(export_instances, export_filters)
        return get_export_download(
            export_instances=export_instances,
            filters=export_filters,
            filename=self._get_filename(export_instances)
        )

    @staticmethod
    def _get_form_data_and_specs(in_data):
        try:
            export_specs = in_data['exports']
            filter_form_data = in_data['form_data']
        except (KeyError, TypeError):
            raise ExportAsyncException(
                _("Request requires a list of exports and filters.")
            )

        return filter_form_data, export_specs

    def _process_filters_and_specs(self, in_data):
        """Returns a the export filters and a list of JSON export specs
        """
        filter_form_data, export_specs = self._get_form_data_and_specs(in_data)
        mobile_user_and_group_slugs = self._get_mobile_user_and_group_slugs(
            filter_form_data[ExpandedMobileWorkerFilter.slug]
        )
        try:
            export_filter = self.get_filters(filter_form_data, mobile_user_and_group_slugs)
        except ExportFormValidationException:
            raise ExportAsyncException(
                _("Form did not validate.")
            )

        return export_filter, export_specs

    def check_if_export_has_data(self, in_data):
        export_filters, export_specs = self._process_filters_and_specs(in_data)
        export_instances = [self._get_export(self.domain, spec['export_id']) for spec in export_specs]

        for instance in export_instances:
            if (get_export_size(instance, export_filters) > 0):
                return True

        return False

    @allow_remote_invocation
    def prepare_custom_export(self, in_data):
        """Uses the current exports download framework (with some nasty filters)
        to return the current download id to POLL for the download status.
        :param in_data: dict passed by the  angular js controller.
        :return: {
            'success': True,
            'download_id': '<some uuid>',
        }
        """
        try:
            download = self._get_download_task(in_data)
        except ExportAsyncException as e:
            return format_angular_error(e.message, log_error=True)
        except XlsLengthException:
            return format_angular_error(
                error_msg=_('This file has more than 256 columns, which is not supported '
                            'by xls. Please change the output type to csv or xlsx to export this '
                            'file.'), log_error=False)
        except Exception:
            return format_angular_error(_("There was an error."), log_error=True)
        send_hubspot_form(HUBSPOT_DOWNLOADED_EXPORT_FORM_ID, self.request)
        return format_angular_success({
            'download_id': download.download_id,
        })

    def _get_filename(self, export_instances):
        if len(export_instances) > 1:
            return "{}_custom_bulk_export_{}".format(
                self.domain,
                date.today().isoformat()
            )
        else:
            return "{} {}".format(
                export_instances[0].name,
                date.today().isoformat()
            )

    def _check_deid_permissions(self, export_instances):
        # if any export is de-identified, check that
        # the requesting domain has access to the deid feature.
        if not self.permissions.has_deid_view_permissions:
            for instance in export_instances:
                if instance.is_deidentified:
                    raise ExportAsyncException(
                        _("You do not have permission to export this "
                        "De-Identified export.")
                    )

    def _check_export_size(self, export_instances, filters):
        count = 0
        for instance in export_instances:
            count += get_export_size(instance, filters)
        if count > MAX_EXPORTABLE_ROWS and not PAGINATED_EXPORTS.enabled(self.domain):
            raise ExportAsyncException(
                _("This export contains %(row_count)s rows. Please change the "
                  "filters to be less than %(max_rows)s rows.") % {
                    'row_count': count,
                    'max_rows': MAX_EXPORTABLE_ROWS
                }
            )

    def _get_mobile_user_and_group_slugs(self, filter_slug):
        matches = self.mobile_user_and_group_slugs_regex.findall(filter_slug)
        return [n[1] for n in matches]


@location_safe
class DownloadNewFormExportView(BaseDownloadExportView):
    urlname = 'new_export_download_forms'
    filter_form_class = EmwfFilterFormExport
    export_filter_class = SubmitHistoryFilter
    show_date_range = True
    page_title = ugettext_noop("Download Form Data Export")
    check_for_multimedia = True
    form_or_case = 'form'

    @property
    def export_list_url(self):
        from corehq.apps.export.views.list import FormExportListView
        return reverse(FormExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            self.timezone,
        )

    @property
    def parent_pages(self):
        from corehq.apps.export.views.list import FormExportListView, DeIdFormExportListView
        if not self.permissions.has_edit_permissions:
            return [{
                'title': DeIdFormExportListView.page_title,
                'url': reverse(DeIdFormExportListView.urlname, args=(self.domain,)),
            }]
        return [{
            'title': FormExportListView.page_title,
            'url': reverse(FormExportListView.urlname, args=(self.domain,)),
        }]

    @allow_remote_invocation
    def has_multimedia(self, in_data):
        """Checks to see if this form export has multimedia available to export
        """
        try:
            export_object = self._get_export(self.domain, self.export_id)
            if isinstance(export_object, ExportInstance):
                has_multimedia = export_object.has_multimedia
            else:
                has_multimedia = forms_have_multimedia(
                    self.domain,
                    export_object.app_id,
                    getattr(export_object, 'xmlns', '')
                )
        except Exception:
            return format_angular_error(_("There was an error"), log_error=True)
        return format_angular_success({
            'hasMultimedia': has_multimedia,
        })

    @allow_remote_invocation
    def prepare_form_multimedia(self, in_data):
        """Gets the download_id for the multimedia zip and sends it to the
        exportDownloadService in download_export.ng.js to begin polling for the
        zip file download.
        """
        try:
            filter_form_data, export_specs = self._get_form_data_and_specs(in_data)
            filter_form = self.filter_form_class(
                self.domain_object, self.timezone, filter_form_data
            )
            if not filter_form.is_valid():
                raise ExportFormValidationException(
                    _("Please check that you've submitted all required filters.")
                )
            download = DownloadBase()
            export_object = self._get_export(self.domain, export_specs[0]['export_id'])
            task_kwargs = self.get_multimedia_task_kwargs(in_data, filter_form, export_object,
                                                          download.download_id)
            from corehq.apps.reports.tasks import build_form_multimedia_zip
            download.set_task(build_form_multimedia_zip.delay(**task_kwargs))
        except Exception:
            return format_angular_error(_("There was an error"), log_error=True)
        return format_angular_success({
            'download_id': download.download_id,
        })

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form


    def _get_export(self, domain, export_id):
        return FormExportInstance.get(export_id)

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        form_filters = filter_form.get_form_filter(
            mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
        )
        return form_filters

    def get_multimedia_task_kwargs(self, in_data, filter_form, export_object, download_id):
        filter_slug = in_data['form_data'][ExpandedMobileWorkerFilter.slug]
        mobile_user_and_group_slugs = self._get_mobile_user_and_group_slugs(filter_slug)
        return filter_form.get_multimedia_task_kwargs(export_object, download_id, mobile_user_and_group_slugs)

    @allow_remote_invocation
    def prepare_custom_export(self, in_data):
        prepare_custom_export = super(DownloadNewFormExportView, self).prepare_custom_export(in_data)

        if self.check_if_export_has_data(in_data):
            track_workflow(self.request.couch_user.username, 'Downloaded Form Exports With Data')
        else:
            track_workflow(self.request.couch_user.username, 'Downloaded Form Exports With No Data')

        return prepare_custom_export


@location_safe
class DownloadNewCaseExportView(BaseDownloadExportView):
    urlname = 'new_export_download_cases'
    filter_form_class = FilterCaseESExportDownloadForm
    export_filter_class = CaseListFilter
    page_title = ugettext_noop("Download Case Data Export")
    form_or_case = 'case'

    @property
    def export_list_url(self):
        from corehq.apps.export.views.list import CaseExportListView
        return reverse(CaseExportListView.urlname, args=(self.domain,))

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            timezone=self.timezone,
        )

    @property
    def parent_pages(self):
        from corehq.apps.export.views.list import CaseExportListView
        return [{
            'title': CaseExportListView.page_title,
            'url': reverse(CaseExportListView.urlname, args=(self.domain,)),
        }]

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data,
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form

    def _get_export(self, domain, export_id):
        return CaseExportInstance.get(export_id)

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        if not self.request.can_access_all_locations:
            accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                self.request.domain,
                self.request.couch_user)
            )
        else:
            accessible_location_ids = None
        form_filters = filter_form.get_case_filter(
            mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
        )
        return form_filters

    @allow_remote_invocation
    def prepare_custom_export(self, in_data):
        prepare_custom_export = super(DownloadNewCaseExportView, self).prepare_custom_export(in_data)

        if self.check_if_export_has_data(in_data):
            track_workflow(self.request.couch_user.username, 'Downloaded Case Exports With Data')
        else:
            track_workflow(self.request.couch_user.username, 'Downloaded Case Exports With No Data')

        return prepare_custom_export


class DownloadNewSmsExportView(BaseDownloadExportView):
    urlname = 'new_export_download_sms'
    page_title = ugettext_noop("Export SMS Messages")
    form_or_case = None
    filter_form_class = FilterSmsESExportDownloadForm
    export_id = None
    sms_export = True

    @property
    def export_list_url(self):
        return None

    @property
    @memoized
    def download_export_form(self):
        return self.filter_form_class(
            self.domain_object,
            timezone=self.timezone,
        )

    @property
    def parent_pages(self):
        return []

    def _get_filter_form(self, filter_form_data):
        filter_form = self.filter_form_class(
            self.domain_object, self.timezone, filter_form_data,
        )
        if not filter_form.is_valid():
            raise ExportFormValidationException()
        return filter_form

    def _get_export(self, domain, export_id):
        include_metadata = MESSAGE_LOG_METADATA.enabled_for_request(self.request)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        return filter_form.get_filter()




class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = ugettext_noop("Download Form Data Exports")
    filter_form_class = EmwfFilterFormExport
    export_filter_class = ExpandedMobileWorkerFilter

    @allow_remote_invocation
    def has_multimedia(self, in_data):
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

