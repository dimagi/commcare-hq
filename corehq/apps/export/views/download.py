import json
from datetime import date
from io import BytesIO

from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseServerError,
    JsonResponse,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.generic import View
from django.views.decorators.http import require_GET, require_POST

from memoized import memoized

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.det.exceptions import DETConfigError
from corehq.apps.export.det.schema_generator import (
    generate_from_export_instance,
)
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, process_email_request

from corehq.apps.analytics.tasks import (
    HUBSPOT_DOWNLOADED_EXPORT_FORM_ID,
    send_hubspot_form,
    track_workflow,
)
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.export.const import MAX_NORMAL_EXPORT_SIZE, ALL_CASE_TYPE_EXPORT
from corehq.apps.export.exceptions import (
    ExportAsyncException,
    ExportFormValidationException,
    CaseTypeOrAppLimitExceeded,
    NoTablesException
)
from corehq.apps.export.export import (
    get_export_download,
    get_export_query,
    get_export_size,
)
from corehq.apps.export.forms import (
    EmwfFilterFormExport,
    FilterCaseESExportDownloadForm,
    FilterSmsESExportDownloadForm,
    DatasourceExportDownloadForm,
)
from corehq.apps.export.models import FormExportInstance
from corehq.apps.export.models.new import EmailExportWhenDoneRequest, datasource_export_instance
from corehq.apps.export.utils import get_export
from corehq.apps.export.views.utils import (
    ExportsPermissionsManager,
    get_timezone,
    case_type_or_app_limit_exceeded
)
from corehq.apps.hqwebapp.decorators import use_daterangepicker
from corehq.apps.hqwebapp.widgets import DateRangePickerWidget
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.analytics.esaccessors import media_export_is_too_big
from corehq.apps.reports.filters.case_list import CaseListFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.tasks import build_form_multimedia_zipfile
from corehq.apps.reports.util import datespan_from_beginning
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.users.models import CouchUser
from corehq.toggles import PAGINATED_EXPORTS
from corehq.util.view_utils import is_ajax
from corehq.toggles import EXPORT_DATA_SOURCE_DATA
from corehq.apps.userreports.models import DataSourceConfiguration


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
        if not is_ajax(request):
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
            and not is_ajax(self.request)
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
    if count > MAX_NORMAL_EXPORT_SIZE and not PAGINATED_EXPORTS.enabled(domain):
        raise ExportAsyncException(
            _("This export contains %(row_count)s rows. Please change the "
              "filters to be less than %(max_rows)s rows.") % {
                'row_count': count,
                'max_rows': MAX_NORMAL_EXPORT_SIZE
            }
        )


def _validate_case_export_instances(domain, export_instances):
    limit_exceeded = case_type_or_app_limit_exceeded(domain)
    for instance in export_instances:
        if limit_exceeded and instance.case_type == ALL_CASE_TYPE_EXPORT:
            raise CaseTypeOrAppLimitExceeded()
        elif not len(instance.tables):
            raise NoTablesException(
                _("There are no sheets to export. If this is a bulk case export then "
                  "the export configuration might still be busy populating its tables. "
                  "Please try again later.")
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
    export_es_filters = [f.to_es_filter() for f in export_filters]

    export_specs = json.loads(request.POST.get('exports'))
    export_ids = [spec['export_id'] for spec in export_specs]
    export_instances = [view_helper.get_export(export_id) for export_id in export_ids]

    try:
        _check_deid_permissions(permissions, export_instances)
        _check_export_size(domain, export_instances, export_filters)
        if form_or_case == 'case':
            _validate_case_export_instances(domain, export_instances)
    except (ExportAsyncException, CaseTypeOrAppLimitExceeded, NoTablesException) as e:
        return json_response({
            'error': str(e),
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
        es_filters=export_es_filters,
        owner_id=request.couch_user.get_id,
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
                'error': _("Failed to download export."),
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
    page_title = gettext_noop("Download Form Data Export")
    check_for_multimedia = True
    form_or_case = 'form'

    @property
    def parent_pages(self):
        from corehq.apps.export.views.list import FormExportListView, DeIdFormExportListView
        if not (self.permissions.has_edit_permissions and self.permissions.has_view_permissions):
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

    export = view_helper.get_export(export_specs[0]['export_id'])
    filters = filter_form.get_export_filters(request, filter_form_data)
    export_es_query = get_export_query(export, filters)

    if media_export_is_too_big(export_es_query):
        return json_response({
            'success': False,
            'error': _("This is too many files to export at once.  "
                       "Please modify your filters to select fewer forms."),
        })

    download = DownloadBase()
    download.set_task(build_form_multimedia_zipfile.delay(
        domain=domain,
        export_id=export.get_id,
        es_filters=filters,
        download_id=download.download_id,
        owner_id=request.couch_user.get_id,
    ))

    return json_response({
        'success': True,
        'download_id': download.download_id,
    })


@require_GET
@location_safe
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
    return json_response({
        'success': True,
        'hasMultimedia': export_object.has_multimedia,
    })


@location_safe
class DownloadNewCaseExportView(BaseDownloadExportView):
    urlname = 'new_export_download_cases'
    export_filter_class = CaseListFilter
    page_title = gettext_noop("Download Case Data Export")
    form_or_case = 'case'

    @property
    def parent_pages(self):
        from corehq.apps.export.views.list import CaseExportListView
        return [{
            'title': CaseExportListView.page_title,
            'url': reverse(CaseExportListView.urlname, args=(self.domain,)),
        }]


@location_safe
class DownloadNewDatasourceExportView(BaseProjectDataView):
    urlname = "data_export_page"
    page_title = gettext_noop("Export Data Source Data")
    template_name = 'export/datasource_export_view.html'

    def dispatch(self, *args, **kwargs):
        if not EXPORT_DATA_SOURCE_DATA.enabled(self.domain):
            raise Http404()
        return super(DownloadNewDatasourceExportView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        context = super(DownloadNewDatasourceExportView, self).page_context
        context["form"] = self.form
        return context

    def post(self, request, *args, **kwargs):
        form = self.form
        if not form.is_valid():
            return HttpResponseBadRequest("Please check your query")

        data_source_id = form.cleaned_data.get('data_source')
        config = DataSourceConfiguration.get(data_source_id)
        return _render_det_download(
            filename=config.display_name,
            export_instance=datasource_export_instance(config),
        )

    @property
    def form(self):
        if self.request.method == 'POST':
            return DatasourceExportDownloadForm(self.domain, self.request.POST)
        return DatasourceExportDownloadForm(self.domain)


class DownloadNewSmsExportView(BaseDownloadExportView):
    urlname = 'new_export_download_sms'
    page_title = gettext_noop("Export SMS Messages")
    form_or_case = None
    export_id = None
    sms_export = True

    @property
    def parent_pages(self):
        return []


class BulkDownloadNewFormExportView(DownloadNewFormExportView):
    urlname = 'new_bulk_download_forms'
    page_title = gettext_noop("Download Form Data Exports")
    export_filter_class = ExpandedMobileWorkerFilter
    check_for_multimedia = False


@login_and_domain_required
@require_POST
def add_export_email_request(request, domain):
    download_id = request.POST.get('download_id')
    user_id = request.couch_user.user_id
    if download_id is None or user_id is None:
        return HttpResponseBadRequest(gettext_lazy('Download ID or User ID blank/not provided'))
    try:
        download_context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError(gettext_lazy('Export failed'))
    if download_context.get('is_ready', False):
        try:
            couch_user = CouchUser.get_by_user_id(user_id, domain=domain)
        except CouchUser.AccountTypeError:
            return HttpResponseBadRequest(gettext_lazy('Invalid user'))
        if couch_user is not None:
            process_email_request(domain, download_id, couch_user.get_email())
    else:
        EmailExportWhenDoneRequest.objects.create(domain=domain, download_id=download_id, user_id=user_id)
    return HttpResponse(gettext_lazy('Export e-mail request sent.'))


@method_decorator(login_and_domain_required, name='dispatch')
class DownloadDETSchemaView(View):
    urlname = 'download-det-schema'

    def get(self, request, domain, export_instance_id):
        export_instance = get_properly_wrapped_export_instance(export_instance_id)
        assert domain == export_instance.domain

        return _render_det_download(
            filename=export_instance.name,
            export_instance=export_instance,
        )


def _render_det_download(filename, export_instance):
    output_file = BytesIO()
    try:
        generate_from_export_instance(export_instance, output_file)
    except DETConfigError as e:
        return HttpResponse(_('Sorry, something went wrong creating that file: {error}').format(error=e))

    output_file.seek(0)
    response = HttpResponse(
        output_file,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}-DET.xlsx"'
    return response
