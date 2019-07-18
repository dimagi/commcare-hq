from __future__ import absolute_import
from __future__ import unicode_literals

import json
import six
from datetime import date

from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from django.http import HttpResponseBadRequest, Http404, HttpResponse, \
    HttpResponseServerError, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from django.views.decorators.http import require_GET, require_POST
from memoized import memoized
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, process_email_request

from corehq.apps.analytics.tasks import send_hubspot_form, HUBSPOT_DOWNLOADED_EXPORT_FORM_ID, track_workflow
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.models import CouchUser
from corehq.couchapps.dbaccessors import forms_have_multimedia
from corehq.toggles import PAGINATED_EXPORTS

from corehq.apps.export.const import MAX_EXPORTABLE_ROWS
from corehq.apps.export.exceptions import ExportFormValidationException, ExportAsyncException
from corehq.apps.export.export import get_export_download, get_export_size
from corehq.apps.export.forms import (
    EmwfFilterFormExport,
    FilterCaseESExportDownloadForm,
    FilterSmsESExportDownloadForm
)
from corehq.apps.export.models import (
    FormExportInstance,
    ExportInstance,
)
from corehq.apps.export.models.new import EmailExportWhenDoneRequest
from corehq.apps.export.views.utils import ExportsPermissionsManager, get_timezone
from corehq.apps.export.utils import get_export


class DownloadExportViewHelper(object):
    '''
    Encapsulates behavior that varies based on model (form, case, or sms)
    and is needed by the function-based views in this module.
    '''

    @classmethod
    def get(self, request, domain, form_or_case, is_sms):
        model = form_or_case if form_or_case else 'sms'
        if model == 'form':
            return FormDownloadExportViewHelper(request, domain)
        elif model == 'case':
            return CaseDownloadExportViewHelper(request, domain)
        elif model == 'sms':
            return SMSDownloadExportViewHelper(request, domain)
        else:
            raise ValueError("Unrecognized model type")

    def __init__(self, request, domain):
        super(DownloadExportViewHelper, self).__init__()
        self.request = request
        self.domain = domain

    def get_export(self, id):
        raise NotImplementedError()

    def send_preparation_analytics(self, export_instances, export_filters):
        send_hubspot_form(HUBSPOT_DOWNLOADED_EXPORT_FORM_ID, self.request)

        track_workflow(self.request.couch_user.username, 'Downloaded {} Exports With {}Data'.format(
            self.model[0].upper() + self.model[1:],
            '' if any(get_export_size(instance, export_filters) > 0 for instance in export_instances) else 'No ',
        ))

    def get_filter_form(self, filter_form_data):
        domain_object = Domain.get_by_name(self.domain)
        timezone = get_timezone(self.domain, self.request.couch_user)
        filter_form = self.filter_form_class(domain_object, timezone, filter_form_data)

        if not filter_form.is_valid():
            raise ExportFormValidationException

        return filter_form


class FormDownloadExportViewHelper(DownloadExportViewHelper):
    model = 'form'
    filter_form_class = EmwfFilterFormExport

    def get_export(self, export_id=None):
        return get_export(self.model, self.domain, export_id)


class CaseDownloadExportViewHelper(DownloadExportViewHelper):
    model = 'case'
    filter_form_class = FilterCaseESExportDownloadForm

    def get_export(self, export_id=None):
        return get_export(self.model, self.domain, export_id)


class SMSDownloadExportViewHelper(DownloadExportViewHelper):
    model = 'sms'
    filter_form_class = FilterSmsESExportDownloadForm

    def get_export(self, export_id=None):
        return get_export(self.model, self.domain, export_id, self.request.couch_user.username)


class BaseDownloadExportView(BaseProjectDataView):
    template_name = 'export/download_export.html'
    http_method_names = ['get', 'post']
    show_date_range = False
    check_for_multimedia = False
    sms_export = False
    # To serve filters for export from mobile_user_and_group_slugs
    export_filter_class = None

    @use_daterangepicker
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
    def view_helper(self):
        return DownloadExportViewHelper.get(self.request, self.domain, self.form_or_case, self.sms_export)

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
            'form_or_case': self.form_or_case,
            'max_column_size': self.max_column_size,
            'show_date_range': self.show_date_range,
            'check_for_multimedia': self.check_for_multimedia,
            'sms_export': self.sms_export,
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
    @memoized
    def download_export_form(self):
        return self.view_helper.filter_form_class(self.domain_object, timezone=self.timezone)

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
            exports = [self.view_helper.get_export(e['id']) for e in raw_export_list]
        elif self.export_id or self.sms_export:
            exports = [self.view_helper.get_export(self.export_id)]

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


def _check_export_size(domain, export_instances, export_filters):
    count = 0
    for instance in export_instances:
        count += get_export_size(instance, export_filters)
    if count > MAX_EXPORTABLE_ROWS and not PAGINATED_EXPORTS.enabled(domain):
        raise ExportAsyncException(
            _("This export contains %(row_count)s rows. Please change the "
              "filters to be less than %(max_rows)s rows.") % {
                'row_count': count,
                'max_rows': MAX_EXPORTABLE_ROWS
            }
        )


def _check_deid_permissions(permissions, export_instances):
    if not permissions.has_deid_view_permissions:
        for instance in export_instances:
            if instance.is_deidentified:
                raise ExportAsyncException(
                    _("You do not have permission to export de-identified exports.")
                )


@require_POST
@login_and_domain_required
@location_safe
def prepare_custom_export(request, domain):
    """Uses the current exports download framework (with some nasty filters)
    to return the current download id to POLL for the download status.
    :return: {
        'success': True,
        'download_id': '<some uuid>',
    }
    """
    form_or_case = request.POST.get('form_or_case')
    sms_export = json.loads(request.POST.get('sms_export'))
    permissions = ExportsPermissionsManager(form_or_case, domain, request.couch_user)
    permissions.access_download_export_or_404()

    view_helper = DownloadExportViewHelper.get(request, domain, form_or_case, sms_export)

    filter_form_data = json.loads(request.POST.get('form_data'))
    try:
        filter_form = view_helper.get_filter_form(filter_form_data)
    except ExportFormValidationException:
        return json_response({
            'error': _("Form did not validate."),
        })
    export_filters = filter_form.get_export_filters(request, filter_form_data)

    export_specs = json.loads(request.POST.get('exports'))
    export_ids = [spec['export_id'] for spec in export_specs]
    export_instances = [view_helper.get_export(export_id) for export_id in export_ids]

    try:
        _check_deid_permissions(permissions, export_instances)
        _check_export_size(domain, export_instances, export_filters)
    except ExportAsyncException as e:
        return json_response({
            'error': six.text_type(e),
        })

    # Generate filename
    if len(export_instances) > 1:
        filename = "{}_custom_bulk_export_{}".format(domain, date.today().isoformat())
    else:
        filename = "{} {}".format(export_instances[0].name, date.today().isoformat())

    download = get_export_download(
        domain,
        export_ids,
        view_helper.model,
        request.couch_user.username,
        filters=export_filters,
        filename=filename,
    )

    view_helper.send_preparation_analytics(export_instances, export_filters)

    return json_response({
        'success': True,
        'download_id': download.download_id,
    })


@require_GET
@login_and_domain_required
@location_safe
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
    except TaskFailedError as e:
        if e.exception_name == 'XlsLengthException':
            return JsonResponse({
                'error': _(
                    'This file has more than 256 columns, which is not supported by xls. '
                    'Please change the output type to csv or xlsx to export this file.')
            })
        else:
            notify_exception(
                request, "Export download failed",
                details={'download_id': download_id, 'errors': e.errors,
                         'exception_name': e.exception_name})

            return JsonResponse({
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
    export_filter_class = ExpandedMobileWorkerFilter
    show_date_range = True
    page_title = ugettext_noop("Download Form Data Export")
    check_for_multimedia = True
    form_or_case = 'form'

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


@require_POST
@login_and_domain_required
def prepare_form_multimedia(request, domain):
    """Gets the download_id for the multimedia zip and sends it to the
    exportDownloadService in download_export.ng.js to begin polling for the
    zip file download.
    """
    form_or_case = request.POST.get('form_or_case')
    sms_export = json.loads(request.POST.get('sms_export'))
    permissions = ExportsPermissionsManager(form_or_case, domain, request.couch_user)
    permissions.access_download_export_or_404()

    view_helper = DownloadExportViewHelper.get(request, domain, form_or_case, sms_export)
    filter_form_data = json.loads(request.POST.get('form_data'))
    export_specs = json.loads(request.POST.get('exports'))
    try:
        filter_form = view_helper.get_filter_form(filter_form_data)
    except ExportFormValidationException:
        return json_response({
            'error': _("Please check that you've submitted all required filters."),
        })

    download = DownloadBase()
    export_object = view_helper.get_export(export_specs[0]['export_id'])
    task_kwargs = filter_form.get_multimedia_task_kwargs(export_object, download.download_id, filter_form_data)
    from corehq.apps.reports.tasks import build_form_multimedia_zip
    download.set_task(build_form_multimedia_zip.delay(**task_kwargs))

    return json_response({
        'success': True,
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
    def parent_pages(self):
        from corehq.apps.export.views.list import CaseExportListView
        return [{
            'title': CaseExportListView.page_title,
            'url': reverse(CaseExportListView.urlname, args=(self.domain,)),
        }]


class DownloadNewSmsExportView(BaseDownloadExportView):
    urlname = 'new_export_download_sms'
    page_title = ugettext_noop("Export SMS Messages")
    form_or_case = None
    export_id = None
    sms_export = True

    @property
    def parent_pages(self):
        return []


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

