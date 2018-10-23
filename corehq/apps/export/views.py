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


def _get_mobile_user_and_group_slugs(filter_slug):
    mobile_user_and_group_slugs_regex = re.compile(
        '(emw=|case_list_filter=|location_restricted_mobile_worker=){1}([^&]*)(&){0,1}'
    )
    matches = mobile_user_and_group_slugs_regex.findall(filter_slug)
    return [n[1] for n in matches]


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

    def access_download_export_or_404(self):
        if not (self.has_edit_permissions or self.has_view_permissions or self.has_deid_view_permissions):
            raise Http404()


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
        return _get_timezone(self.domain, self.request.couch_user)

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
            'form_or_case': self.form_or_case,
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

    def _process_filters_and_specs(self, in_data):
        """Returns a the export filters and a list of JSON export specs
        """
        filter_form_data = in_data['form_data']
        export_specs = in_data['exports']
        mobile_user_and_group_slugs = _get_mobile_user_and_group_slugs(
            filter_form_data[ExpandedMobileWorkerFilter.slug]
        )
        try:
            # Determine export filter
            filter_form = self._get_filter_form(filter_form_data)
            if self.form_or_case:
                if not self.request.can_access_all_locations:
                    accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                        self.request.domain,
                        self.request.couch_user)
                    )
                else:
                    accessible_location_ids = None

                if self.form_or_case == 'form':
                    export_filter = filter_form.get_form_filter(
                        mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
                    )
                elif self.form_or_case == 'case':
                    export_filter = filter_form.get_case_filter(
                        mobile_user_and_group_slugs, self.request.can_access_all_locations, accessible_location_ids
                    )
            else:
                export_filter = filter_form.get_filter()
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

        # Analytics
        if self.form_or_case:
            capitalized = self.form_or_case[0].upper() + self.form_or_case[1:]
            if self.check_if_export_has_data(in_data):
                track_workflow(self.request.couch_user.username,
                               'Downloaded {} Exports With Data'.format(capitalized))
            else:
                track_workflow(self.request.couch_user.username,
                               'Downloaded {} Exports With No Data'.format(capitalized))

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


@require_GET
@login_and_domain_required
def has_multimedia(request, domain):
    """Checks to see if this form export has multimedia available to export
    """
    form_or_case = request.GET.get('form_or_case')
    if form_or_case != 'form':
        raise ValueError("has_multimedia is only available for form exports")

    permissions = ExportsPermissionsManager(form_or_case, domain, request.couch_user)
    permissions.access_download_export_or_404()

    export_object = FormExportInstance.get(request.GET.get('export_id'))
    if isinstance(export_object, ExportInstance):
        has_multimedia = export_object.has_multimedia
    else:
        has_multimedia = forms_have_multimedia(
            domain,
            export_object.app_id,
            getattr(export_object, 'xmlns', '')
        )
    return json_response({
        'success': True,
        'hasMultimedia': has_multimedia,
    })


@require_GET
@login_and_domain_required
def poll_custom_export_download(request, domain):
    """Polls celery to see how the export download task is going.
    :return: final response: {
        'success': True,
        'dropbox_url': '<url>',
        'download_url: '<url>',
        <task info>
    }
    """
    form_or_case = request.GET.get('form_or_case')
    permissions = ExportsPermissionsManager(form_or_case, domain, request.couch_user)
    permissions.access_download_export_or_404()

    download_id = request.GET.get('download_id')
    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        notify_exception(request, "Export download failed",
                         details={'download_id': download_id})
        return json_response({
            'error': _("Download task failed to start."),
        })
    if context.get('is_ready', False):
        context.update({
            'dropbox_url': reverse('dropbox_upload', args=(download_id,)),
            'download_url': "{}?get_file".format(
                reverse('retrieve_download', args=(download_id,))
            ),
        })
    context['is_poll_successful'] = True
    return json_response(context)


class BaseExportListView(HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/export_list.html'
    allow_bulk_export = True
    is_deid = False

    lead_text = ugettext_lazy('''
        Exports are a way to download data in a variety of formats (CSV, Excel, etc.)
        for use in third-party data analysis tools.
    ''')

    @use_select2
    @use_angular_js
    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        self.permissions = ExportsPermissionsManager(self.form_or_case, request.domain, request.couch_user)

        if not (self.permissions.has_edit_permissions or self.permissions.has_view_permissions
                or (self.is_deid and self.permissions.has_deid_view_permissions)):
            raise Http404()

        return super(BaseExportListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'exports': self.get_exports_list(),
            'create_export_form': self.create_export_form if not self.is_deid else None,
            'create_export_form_title': self.create_export_form_title if not self.is_deid else None,
            'bulk_download_url': self.bulk_download_url,
            'allow_bulk_export': self.allow_bulk_export,
            'has_edit_permissions': self.permissions.has_edit_permissions,
            'is_deid': self.is_deid,
            "export_type_caps": _("Export"),
            "export_type": _("export"),
            "export_type_caps_plural": _("Exports"),
            "export_type_plural": _("exports"),
            'my_export_type': _('My Exports'),
            'shared_export_type': _('Exports Shared with Me'),
            "model_type": self.form_or_case,
            "static_model_type": True,
            'max_exportable_rows': MAX_EXPORTABLE_ROWS,
            'lead_text': self.lead_text,
        }

    @property
    def bulk_download_url(self):
        """Returns url for bulk download
        """
        if not self.allow_bulk_export:
            return None
        raise NotImplementedError('must implement bulk_download_url')

    @memoized
    def get_saved_exports(self):
        """The source of the data that will be processed by fmt_export_data
        for use in the template.
        """
        raise NotImplementedError("must implement get_saved_exports")

    @property
    @memoized
    def emailed_export_groups(self):
        """The groups of saved exports by domain for daily emailed exports.
        """
        return HQGroupExportConfiguration.by_domain(self.domain)

    @property
    def daily_emailed_exports(self):
        """Returns a list of exports marked for a daily email.
        """
        raise NotImplementedError("must implement daily_emailed_exports")

    def fmt_export_data(self, export):
        """Returns the object used for each row (per export)
        in the saved exports table. This data will eventually be processed as
        a JSON object by angular.js.
        :return dict
        """
        raise NotImplementedError("must implement fmt_export_data")

    def _get_daily_saved_export_metadata(self, export):
        """
        Return a dictionary containing details about an emailed export.
        This will eventually be passed to an Angular controller.
        """

        has_file = export.has_file()
        file_data = {}
        if has_file:
            download_url = self.request.build_absolute_uri(
                reverse('download_daily_saved_export', args=[self.domain, export._id]))
            file_data = self._fmt_emailed_export_fileData(
                export._id, export.file_size, export.last_updated,
                export.last_accessed, download_url
            )

        location_restrictions = []
        locations = []
        filters = export.filters
        if filters.accessible_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=filters.accessible_location_ids)
        for location in locations:
            location_restrictions.append(location.display_name)

        return {
            'groupId': None,  # This can be removed when we're off legacy exports
            'hasFile': has_file,
            'index': None,  # This can be removed when we're off legacy exports
            'fileData': file_data,
            'filters': DashboardFeedFilterForm.get_form_data_from_export_instance_filters(
                filters, self.domain, type(export)
            ),
            'isLocationSafeForUser': filters.is_location_safe_for_user(self.request),
            'locationRestrictions': location_restrictions,
            'taskStatus': self._get_task_status_json(export._id),
        }

    def _fmt_emailed_export_fileData(self, fileId, size, last_updated,
                                     last_accessed, download_url):
        """
        Return a dictionary containing details about an emailed export file.
        This will eventually be passed to an Angular controller.
        """
        return {
            'fileId': fileId,
            'size': filesizeformat(size),
            'lastUpdated': naturaltime(last_updated),
            'lastAccessed': naturaltime(last_accessed),
            'showExpiredWarning': (
                last_accessed and
                last_accessed <
                (datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF))
            ),
            'downloadUrl': download_url,
        }

    def get_exports_list(self):
        # Calls self.get_saved_exports and formats each item using self.fmt_export_data
        saved_exports = self.get_saved_exports()
        if toggles.EXPORT_OWNERSHIP.enabled(self.request.domain):
            saved_exports = [
                export for export in saved_exports
                if export.can_view(self.request.couch_user.user_id)
            ]
        if self.is_deid:
            saved_exports = [x for x in saved_exports if x.is_safe]
        return list(map(self.fmt_export_data, saved_exports))

    @property
    def create_export_form_title(self):
        """Returns a string that is displayed as the title of the create
        export form below.
        """
        raise NotImplementedError("must implement create_export_form_title")

    @property
    def create_export_form(self):
        """Returns a django form that gets the information necessary to create
        an export tag, which is the first step in creating a new export.

        This form is what will interact with the DrilldownToFormController in
        hq.app_data_drilldown.ng.js
        """
        if self.permissions.has_case_export_permissions or self.permissions.has_form_export_permissions:
            return CreateExportTagForm(self.permissions.has_form_export_permissions,
                                       self.permissions.has_case_export_permissions)

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        """Called by the ANGULAR.JS controller DrilldownToFormController in
        hq.app_data_drilldown.ng.js  Use ApplicationDataRMIHelper to help
        format the response.
        """
        raise NotImplementedError("Must implement get_intial_form_data")

    def get_create_export_url(self, form_data):
        """Returns url to the custom export creation form with the export
        tag appended.
        """
        raise NotImplementedError("Must implement generate_create_form_url")

    @allow_remote_invocation
    def toggle_saved_export_enabled_state(self, in_data):
        export_instance_id = in_data['export']['id']
        export_instance = get_properly_wrapped_export_instance(export_instance_id)
        export_instance.auto_rebuild_enabled = not in_data['export']['isAutoRebuildEnabled']
        export_instance.save()
        return format_angular_success({
            'isAutoRebuildEnabled': export_instance.auto_rebuild_enabled
        })

    @allow_remote_invocation
    def update_emailed_export_data(self, in_data):
        export_instance_id = in_data['export']['id']
        rebuild_saved_export(export_instance_id, manual=True)
        return format_angular_success({})

    @allow_remote_invocation
    def submit_app_data_drilldown_form(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            form_data = in_data['formData']
        except KeyError:
            return format_angular_error(
                _("The form's data was not correctly formatted."),
                log_error=False,
            )
        try:
            create_url = self.get_create_export_url(form_data)
        except ExportFormValidationException:
            return format_angular_error(
                _("The form did not validate."),
                log_error=False,
            )
        except Exception as e:
            return format_angular_error(
                _("Problem getting link to custom export form: {}").format(e),
                log_error=False,
            )
        return format_angular_success({
            'url': create_url,
        })

    @staticmethod
    def _get_task_status_json(export_instance_id):
        status = get_saved_export_task_status(export_instance_id)
        return {
            'percentComplete': status.progress.percent or 0,
            'inProgress': status.started(),
            'success': status.success(),
        }

    @allow_remote_invocation
    def get_saved_export_progress(self, in_data):
        return format_angular_success({
            'taskStatus': self._get_task_status_json(in_data['export_instance_id']),
        })


@location_safe
class DailySavedExportListView(BaseExportListView):
    urlname = 'list_daily_saved_exports'
    page_title = ugettext_lazy("Daily Saved Exports")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    def dispatch(self, *args, **kwargs):
        if not self._priv_check():
            raise Http404
        return super(DailySavedExportListView, self).dispatch(*args, **kwargs)

    def _priv_check(self):
        return domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)

    def _get_create_export_class(self, model):
        return {
            "form": CreateNewDailySavedFormExport,
            "case": CreateNewDailySavedCaseExport,
        }[model]

    def _get_edit_export_class(self, model):
        return {
            "form": EditFormDailySavedExportView,
            "case": EditCaseDailySavedExportView
        }[model]

    @property
    def page_context(self):
        context = super(DailySavedExportListView, self).page_context
        model_type = None
        if self.permissions.has_form_export_permissions and not self.permissions.has_case_export_permissions:
            model_type = "form"
        if not self.permissions.has_form_export_permissions and self.permissions.has_case_export_permissions:
            model_type = "case"
        context.update({
            "is_daily_saved_export": True,
            "model_type": model_type,
            "static_model_type": False,
            "export_filter_form": DashboardFeedFilterForm(
                self.domain_object,
            )
        })
        return context

    @property
    @memoized
    def create_export_form_title(self):
        return "Select a model to export"  # could be form or case

    @property
    def bulk_download_url(self):
        # Daily Saved exports do not support bulk download
        return ""

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.permissions.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        if self.permissions.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and not x.export_format == "html"]

    @property
    def daily_emailed_exports(self):
        # This function only returns old-style exports. Since this view will only be visible for people using new
        # exports, it need not return anything.
        return []

    def fmt_export_data(self, export):
        if isinstance(export, FormExportInstance):
            edit_view = self._get_edit_export_class('form')
            download_view = DownloadNewFormExportView
            formname = export.formname
        else:
            edit_view = self._get_edit_export_class('case')
            download_view = DownloadNewCaseExportView
            formname = None

        emailed_export = self._get_daily_saved_export_metadata(export)

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'description': export.description,
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': (
                WebUser.get_by_user_id(export.owner_id).username
                if export.owner_id else UNKNOWN_EXPORT_OWNER
            ),
            'can_edit': export.can_edit(self.request.couch_user),
            'formname': formname,
            'addedToBulk': False,
            'exportType': export.type,
            'isDailySaved': True,
            'isAutoRebuildEnabled': export.auto_rebuild_enabled,
            'emailedExport': emailed_export,
            'editUrl': reverse(edit_view.urlname, args=(self.domain, export.get_id)),
            'downloadUrl': reverse(download_view.urlname, args=(self.domain, export.get_id)),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_dual_model_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Daily Saved Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.permissions.has_form_export_permissions,
            self.permissions.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()

        if create_form.cleaned_data['model_type'] == "case":
            export_tag = create_form.cleaned_data['case_type']
            cls = self._get_create_export_class('case')
        else:
            export_tag = create_form.cleaned_data['form']
            cls = self._get_create_export_class('form')
        app_id = create_form.cleaned_data['application']
        app_id_param = '&app_id={}'.format(app_id) if app_id != ApplicationDataRMIHelper.UNKNOWN_SOURCE else ""

        return reverse(
            cls.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id_param}'.format(
            app_id_param=app_id_param,
            export_tag=export_tag,
        ))

    @allow_remote_invocation
    def commit_filters(self, in_data):
        if not self.permissions.has_edit_permissions:
            raise Http404

        export_id = in_data['export']['id']
        form_data = in_data['form_data']
        try:
            export = get_properly_wrapped_export_instance(export_id)

            if not export.filters.is_location_safe_for_user(self.request):
                return location_restricted_response(self.request)

            filter_form = DashboardFeedFilterForm(self.domain_object, form_data)
            if filter_form.is_valid():
                old_can_access_all_locations = export.filters.can_access_all_locations
                old_accessible_location_ids = export.filters.accessible_location_ids

                filters = filter_form.to_export_instance_filters(
                    # using existing location restrictions prevents a less restricted user from modifying
                    # restrictions on an export that a more restricted user created (which would mean the more
                    # restricted user would lose access to the export)
                    old_can_access_all_locations,
                    old_accessible_location_ids
                )
                if export.filters != filters:
                    export.filters = filters
                    export.save()
                    rebuild_saved_export(export_id, manual=True)
                return format_angular_success()
            else:
                return format_angular_error(
                    _("Problem saving dashboard feed filters: Invalid form"),
                    log_error=True)
        except Exception:
            return format_angular_error(_("Problem saving dashboard feed filters"),
                                        log_error=True)


@location_safe
class DashboardFeedListView(DailySavedExportListView):
    urlname = 'list_dashboard_feeds'
    page_title = ugettext_lazy("Excel Dashboard Integration")
    form_or_case = None  # This view lists both case and form feeds
    allow_bulk_export = False

    lead_text = ugettext_lazy('''
        Excel dashboard feeds allow Excel to directly connect to CommCareHQ to download data.
        Data is updated daily.
    ''')

    def _priv_check(self):
        return domain_has_privilege(self.domain, EXCEL_DASHBOARD)

    def _get_create_export_class(self, model):
        return {
            "form": CreateNewFormFeedView,
            "case": CreateNewCaseFeedView,
        }[model]

    def _get_edit_export_class(self, model):
        return {
            "form": EditFormFeedView,
            "case": EditCaseFeedView
        }[model]

    @property
    def page_context(self):
        context = super(DashboardFeedListView, self).page_context
        context.update({
            "export_type_caps": _("Dashboard Feed"),
            "export_type": _("dashboard feed"),
            "export_type_caps_plural": _("Dashboard Feeds"),
            "export_type_plural": _("dashboard feeds"),
            'my_export_type': _('My Dashboard Feeds'),
            'shared_export_type': _('Dashboard Feeds Shared with Me'),
        })
        return context

    def fmt_export_data(self, export):
        data = super(DashboardFeedListView, self).fmt_export_data(export)
        data.update({
            'isFeed': True,
        })
        return data

    @memoized
    def get_saved_exports(self):
        combined_exports = []
        if self.permissions.has_form_export_permissions:
            combined_exports.extend(get_form_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        if self.permissions.has_case_export_permissions:
            combined_exports.extend(get_case_exports_by_domain(self.domain,
                                                               self.permissions.has_deid_view_permissions))
        combined_exports = sorted(combined_exports, key=lambda x: x.name)
        return [x for x in combined_exports if x.is_daily_saved_export and x.export_format == "html"]


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


@location_safe
class FormExportListView(BaseExportListView):
    urlname = 'list_form_exports'
    page_title = ugettext_noop("Export Form Data")
    form_or_case = 'form'

    @property
    def bulk_download_url(self):
        return reverse(BulkDownloadNewFormExportView.urlname, args=(self.domain,))

    @memoized
    def get_saved_exports(self):
        exports = get_form_exports_by_domain(self.domain, self.permissions.has_deid_view_permissions)
        # New exports display daily saved exports in their own view
        return [x for x in exports if not x.is_daily_saved_export]

    @property
    @memoized
    def daily_emailed_exports(self):
        all_form_exports = []
        for group in self.emailed_export_groups:
            all_form_exports.extend(group.form_exports)
        return all_form_exports

    @property
    def create_export_form_title(self):
        return _("Select a Form to Export")

    def fmt_export_data(self, export):
        emailed_export = None
        if export.is_daily_saved_export:
            emailed_export = self._get_daily_saved_export_metadata(export)
        owner_username = (
            WebUser.get_by_user_id(export.owner_id).username
            if export.owner_id else UNKNOWN_EXPORT_OWNER
        )

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'description': export.description,
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': owner_username,
            'can_edit': export.can_edit(self.request.couch_user),
            'formname': export.formname,
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(EditNewCustomFormExportView.urlname,
                               args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export.get_id),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id):
        return reverse(DownloadNewFormExportView.urlname, args=(self.domain, export_id))

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        if self.is_deid:
            raise Http404()
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_form_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.permissions.has_form_export_permissions,
            self.permissions.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()

        app_id = create_form.cleaned_data['application']
        form_xmlns = create_form.cleaned_data['form']
        return reverse(
            CreateNewCustomFormExportView.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id}'.format(
            app_id=('&app_id={}'.format(app_id)
                    if app_id != ApplicationDataRMIHelper.UNKNOWN_SOURCE else ""),
            export_tag=form_xmlns,
        ))


class DeIdFormExportListView(FormExportListView):
    page_title = ugettext_noop("Export De-Identified Form Data")
    urlname = 'list_form_deid_exports'
    is_deid = True

    @property
    def create_export_form(self):
        return None


class _DeidMixin(object):
    is_deid = True

    @property
    def create_export_form(self):
        return None

    def get_saved_exports(self):
        return [x for x in get_form_export_instances(self.domain) if x.is_safe]


@location_safe
class DeIdDailySavedExportListView(_DeidMixin, DailySavedExportListView):
    urlname = 'list_deid_daily_saved_exports'
    page_title = ugettext_noop("Export De-Identified Daily Saved Exports")

    def get_saved_exports(self):
        exports = super(DeIdDailySavedExportListView, self).get_saved_exports()
        return [x for x in exports if x.is_daily_saved_export and not x.export_format == "html"]


@location_safe
class DeIdDashboardFeedListView(_DeidMixin, DashboardFeedListView):
    urlname = 'list_deid_dashboard_feeds'
    page_title = ugettext_noop("Export De-Identified Dashboard Feeds")

    def get_saved_exports(self):
        exports = super(DeIdDashboardFeedListView, self).get_saved_exports()
        return [x for x in exports if x.is_daily_saved_export and x.export_format == "html"]


@location_safe
class CaseExportListView(BaseExportListView):
    urlname = 'list_case_exports'
    page_title = ugettext_noop("Export Case Data")
    allow_bulk_export = False
    form_or_case = 'case'

    @property
    def page_name(self):
        if self.is_deid:
            return _("Export De-Identified Cases")
        return self.page_title

    @property
    @memoized
    def daily_emailed_exports(self):
        all_case_exports = []
        for group in self.emailed_export_groups:
            all_case_exports.extend(group.case_exports)
        return all_case_exports

    @memoized
    def get_saved_exports(self):
        exports = get_case_exports_by_domain(self.domain, self.permissions.has_deid_view_permissions)
        return [x for x in exports if not x.is_daily_saved_export]

    @property
    def create_export_form_title(self):
        return _("Select a Case Type to Export")

    def fmt_export_data(self, export):
        emailed_export = None
        if export.is_daily_saved_export:
            emailed_export = self._get_daily_saved_export_metadata(export)
        owner_username = (
            WebUser.get_by_user_id(export.owner_id).username
            if export.owner_id else UNKNOWN_EXPORT_OWNER
        )

        return {
            'id': export.get_id,
            'isDeid': export.is_safe,
            'name': export.name,
            'case_type': export.case_type,
            'description': export.description,
            'my_export': export.owner_id == self.request.couch_user.user_id,
            'sharing': export.sharing,
            'owner_username': owner_username,
            'can_edit': export.can_edit(self.request.couch_user),
            'addedToBulk': False,
            'exportType': export.type,
            'emailedExport': emailed_export,
            'editUrl': reverse(EditNewCustomCaseExportView.urlname, args=(self.domain, export.get_id)),
            'downloadUrl': self._get_download_url(export._id),
            'copyUrl': reverse(CopyExportView.urlname, args=(self.domain, export.get_id)),
        }

    def _get_download_url(self, export_id):
        return reverse(DownloadNewCaseExportView.urlname, args=(self.domain, export_id))

    @allow_remote_invocation
    def get_app_data_drilldown_values(self, in_data):
        try:
            rmi_helper = ApplicationDataRMIHelper(self.domain, self.request.couch_user)
            response = rmi_helper.get_case_rmi_response()
        except Exception:
            return format_angular_error(
                _("Problem getting Create Export Form"),
                log_error=True,
            )
        return format_angular_success(response)

    def get_create_export_url(self, form_data):
        create_form = CreateExportTagForm(
            self.permissions.has_form_export_permissions,
            self.permissions.has_case_export_permissions,
            form_data
        )
        if not create_form.is_valid():
            raise ExportFormValidationException()
        case_type = create_form.cleaned_data['case_type']
        app_id = create_form.cleaned_data['application']
        if app_id == ApplicationDataRMIHelper.UNKNOWN_SOURCE:
            app_id_param = ''
        else:
            app_id_param = '&app_id={}'.format(app_id)

        return reverse(
            CreateNewCustomCaseExportView.urlname,
            args=[self.domain],
        ) + ('?export_tag="{export_tag}"{app_id_param}'.format(
            export_tag=case_type,
            app_id_param=app_id_param,
        ))


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
        return DashboardFeedListView


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
    def prepare_form_multimedia(self, in_data):
        """Gets the download_id for the multimedia zip and sends it to the
        exportDownloadService in download_export.ng.js to begin polling for the
        zip file download.
        """
        try:
            filter_form_data = in_data['form_data']
            export_specs = in_data['exports']
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

    def get_multimedia_task_kwargs(self, in_data, filter_form, export_object, download_id):
        filter_slug = in_data['form_data'][ExpandedMobileWorkerFilter.slug]
        mobile_user_and_group_slugs = _get_mobile_user_and_group_slugs(filter_slug)
        return filter_form.get_multimedia_task_kwargs(export_object, download_id, mobile_user_and_group_slugs)


class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = ugettext_noop("Download Form Data Exports")
    filter_form_class = EmwfFilterFormExport
    export_filter_class = ExpandedMobileWorkerFilter
    check_for_multimedia = False


@location_safe
class DownloadNewCaseExportView(BaseDownloadExportView):
    urlname = 'new_export_download_cases'
    filter_form_class = FilterCaseESExportDownloadForm
    export_filter_class = CaseListFilter
    page_title = ugettext_noop("Download Case Data Export")
    form_or_case = 'case'

    @property
    def export_list_url(self):
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
