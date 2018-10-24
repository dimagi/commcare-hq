from __future__ import absolute_import

from __future__ import division
from __future__ import unicode_literals
from datetime import date

from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404, HttpResponse, \
    HttpResponseServerError
from django.views.decorators.http import require_GET, require_POST

from corehq.apps.analytics.tasks import send_hubspot_form, HUBSPOT_DOWNLOADED_EXPORT_FORM_ID
from corehq.toggles import MESSAGE_LOG_METADATA, PAGINATED_EXPORTS
from corehq.apps.export.exceptions import ExportNotFound
from corehq.apps.export.export import get_export_download, get_export_size
from corehq.apps.export.models.new import EmailExportWhenDoneRequest
from corehq.apps.export.views.utils import ExportsPermissionsManager, get_timezone
from corehq.apps.hqwebapp.views import HQJSONResponseMixin
from corehq.apps.hqwebapp.utils import format_angular_error, format_angular_success
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter, SubmitHistoryFilter
from corehq.apps.reports.models import HQUserType
from django.utils.decorators import method_decorator
import json
import re

from couchexport.writers import XlsLengthException

from djangular.views.mixins import allow_remote_invocation
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.apps.domain.decorators import login_and_domain_required
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
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.hqwebapp.decorators import (
    use_select2,
    use_daterangepicker,
    use_jquery_ui,
    use_ko_validation,
    use_angular_js)
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget
from corehq.apps.users.models import CouchUser
from corehq.apps.analytics.tasks import track_workflow
from memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from dimagi.utils.logging import notify_exception
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, process_email_request


def _get_export(request, domain=None, export_id=None, form_or_case=None, sms_export=False):
    if sms_export:
        include_metadata = MESSAGE_LOG_METADATA.enabled_for_request(request)
        return SMSExportInstance._new_from_schema(
            SMSExportDataSchema.get_latest_export_schema(domain, include_metadata)
        )
    if form_or_case == 'form':
        return FormExportInstance.get(export_id)
    if form_or_case == 'case':
        return CaseExportInstance.get(export_id)
    raise ExportNotFound("Could not get export")


# Form used for rendering filters
def _get_filter_form_class(form_or_case, sms_export=False):
    if sms_export:
        return FilterSmsESExportDownloadForm
    if form_or_case == 'form':
        return EmwfFilterFormExport
    if form_or_case == 'case':
        return FilterCaseESExportDownloadForm
    raise ValueError("Could not find filter form class")


def _get_mobile_user_and_group_slugs(filter_slug):
    mobile_user_and_group_slugs_regex = re.compile(
        '(emw=|case_list_filter=|location_restricted_mobile_worker=){1}([^&]*)(&){0,1}'
    )
    matches = mobile_user_and_group_slugs_regex.findall(filter_slug)
    return [n[1] for n in matches]


class BaseDownloadExportView(HQJSONResponseMixin, BaseProjectDataView):
    template_name = 'export/download_export.html'
    http_method_names = ['get', 'post']
    show_date_range = False
    check_for_multimedia = False
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
    @memoized
    def download_export_form(self):
        form_class = _get_filter_form_class(self.form_or_case, self.sms_export)
        return form_class(self.domain_object, timezone=self.timezone)

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
            exports = [_get_export(
                self.request, domain=self.domain, export_id=e['id'],
                form_or_case=self.form_or_case, sms_export=self.sms_export
            ) for e in raw_export_list]
        elif self.export_id or self.sms_export:
            exports = [_get_export(self.request, domain=self.domain, export_id=self.export_id,
                                   form_or_case=self.form_or_case, sms_export=self.sms_export)]

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

    @property
    def max_column_size(self):
        try:
            return int(self.request.GET.get('max_column_size', 2000))
        except TypeError:
            return 2000

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
            filter_form_data = in_data['form_data']
            export_specs = in_data['exports']
            mobile_user_and_group_slugs = _get_mobile_user_and_group_slugs(
                filter_form_data[ExpandedMobileWorkerFilter.slug]
            )
            try:
                # Determine export filter
                form_class = _get_filter_form_class(self.form_or_case, self.sms_export)
                filter_form = form_class(self.domain_object, self.timezone, filter_form_data)
                if not filter_form.is_valid():
                    raise ExportFormValidationException()
                if self.form_or_case:
                    if not self.request.can_access_all_locations:
                        accessible_location_ids = (SQLLocation.active_objects.accessible_location_ids(
                            self.request.domain,
                            self.request.couch_user)
                        )
                    else:
                        accessible_location_ids = None

                    if self.form_or_case == 'form':
                        export_filters = filter_form.get_form_filter(
                            mobile_user_and_group_slugs, self.request.can_access_all_locations,
                            accessible_location_ids
                        )
                    elif self.form_or_case == 'case':
                        export_filters = filter_form.get_case_filter(
                            mobile_user_and_group_slugs, self.request.can_access_all_locations,
                            accessible_location_ids
                        )
                else:
                    export_filters = filter_form.get_filter()
            except ExportFormValidationException:
                raise ExportAsyncException(
                    _("Form did not validate.")
                )
            export_instances = [_get_export(
                self.request, domain=self.domain, export_id=spec['export_id'],
                form_or_case=self.form_or_case, sms_export=self.sms_export
            ) for spec in export_specs]

            # If any export is de-identified, check that
            # the requesting domain has access to the deid feature.
            if not self.permissions.has_deid_view_permissions:
                for instance in export_instances:
                    if instance.is_deidentified:
                        raise ExportAsyncException(
                            _("You do not have permission to export de-identified exports.")
                        )

            # Check export isn't too big to download
            count = 0
            for instance in export_instances:
                count += get_export_size(instance, export_filters)
            if count > MAX_EXPORTABLE_ROWS and not PAGINATED_EXPORTS.enabled(self.domain):
                raise ExportAsyncException(
                    _("This export contains %(row_count)s rows. Please change the "
                      "filters to be less than %(max_rows)s rows.") % {
                        'row_count': count,
                        'max_rows': MAX_EXPORTABLE_ROWS
                    }
                )

            # Generate filename
            if len(export_instances) > 1:
                filename = "{}_custom_bulk_export_{}".format(self.domain, date.today().isoformat())
            else:
                filename = "{} {}".format(export_instances[0].name, date.today().isoformat())

            download = get_export_download(
                export_instances=export_instances,
                filters=export_filters,
                filename=filename,
            )
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
            def _check_if_export_has_data(instances):
                for instance in instances:
                    if (get_export_size(instance, export_filters) > 0):
                        return True
                return False

            capitalized = self.form_or_case[0].upper() + self.form_or_case[1:]
            if _check_if_export_has_data(export_instances):
                track_workflow(self.request.couch_user.username,
                               'Downloaded {} Exports With Data'.format(capitalized))
            else:
                track_workflow(self.request.couch_user.username,
                               'Downloaded {} Exports With No Data'.format(capitalized))

        return format_angular_success({
            'download_id': download.download_id,
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


@location_safe
class DownloadNewFormExportView(BaseDownloadExportView):
    urlname = 'new_export_download_forms'
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
    def prepare_form_multimedia(self, in_data):
        """Gets the download_id for the multimedia zip and sends it to the
        exportDownloadService in download_export.ng.js to begin polling for the
        zip file download.
        """
        try:
            filter_form_data = in_data['form_data']
            export_specs = in_data['exports']
            form_class = _get_filter_form_class(self.form_or_class, self.sms_export)
            filter_form = form_class(self.domain_object, self.timezone, filter_form_data)
            if not filter_form.is_valid():
                raise ExportFormValidationException(
                    _("Please check that you've submitted all required filters.")
                )
            download = DownloadBase()
            export_object = _get_export(self.request, domain=self.domain, export_id=export_specs[0]['export_id'],
                                        form_or_case=self.form_or_case, sms_export=self.sms_export)
            filter_slug = in_data['form_data'][ExpandedMobileWorkerFilter.slug]
            mobile_user_and_group_slugs = _get_mobile_user_and_group_slugs(filter_slug)
            task_kwargs = filter_form.get_multimedia_task_kwargs(export_object, download.download_id,
                                                                 mobile_user_and_group_slugs)
            from corehq.apps.reports.tasks import build_form_multimedia_zip
            download.set_task(build_form_multimedia_zip.delay(**task_kwargs))
        except Exception:
            return format_angular_error(_("There was an error"), log_error=True)
        return format_angular_success({
            'download_id': download.download_id,
        })


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


@location_safe
class DownloadNewCaseExportView(BaseDownloadExportView):
    urlname = 'new_export_download_cases'
    export_filter_class = CaseListFilter
    page_title = ugettext_noop("Download Case Data Export")
    form_or_case = 'case'

    @property
    def export_list_url(self):
        from corehq.apps.export.views.list import CaseExportListView
        return reverse(CaseExportListView.urlname, args=(self.domain,))

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


class DownloadNewSmsExportView(BaseDownloadExportView):
    urlname = 'new_export_download_sms'
    page_title = ugettext_noop("Export SMS Messages")
    form_or_case = None
    export_id = None
    sms_export = True

    @property
    def export_list_url(self):
        return None

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

    def get_filters(self, filter_form_data, mobile_user_and_group_slugs):
        filter_form = self._get_filter_form(filter_form_data)
        return filter_form.get_filter()




class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = ugettext_noop("Download Form Data Exports")
    export_filter_class = ExpandedMobileWorkerFilter
    check_for_multimedia = False


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

