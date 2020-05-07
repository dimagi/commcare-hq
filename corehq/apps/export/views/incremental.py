from wsgiref.util import FileWrapper

from django.http import HttpResponseNotFound, StreamingHttpResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
from django.views.generic import FormView

from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.export.forms import (
    IncrementalExportFormSet,
    IncrementalExportFormSetHelper,
)
from corehq.apps.export.models.incremental import (
    IncrementalExport,
    IncrementalExportCheckpoint,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.settings.views import BaseProjectDataView
from corehq.motech.views import MotechLogDetailView
from corehq.toggles import INCREMENTAL_EXPORTS


@method_decorator(INCREMENTAL_EXPORTS.required_decorator(), name='dispatch')
class IncrementalExportView(BaseProjectDataView, FormView):
    urlname = 'incremental_export_view'
    page_title = ugettext_lazy('Incremental Export')
    template_name = 'export/incremental_export.html'
    form_class = IncrementalExportFormSet

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # BaseIncrementalExportFormSet needs request to add to its
        # form_kwargs. IncrementalExportForm needs it to populate the
        # case export instance select box, and to set
        # IncrementalExport.domain when the model instance is saved.
        kwargs['request'] = self.request
        kwargs['queryset'] = IncrementalExport.objects.filter(domain=self.domain)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['helper'] = IncrementalExportFormSetHelper()
        return context

    def get_success_url(self):
        # On save, stay on the same page
        return reverse(self.urlname, kwargs={'domain': self.domain})

    def form_valid(self, form):
        self.object = form.save()  # Saves the forms in the formset
        return super().form_valid(form)


class IncrementalExportLogView(GenericTabularReport, DatespanMixin):
    name = 'Incremental Export Logs'
    base_template = 'reports/base_template.html'
    section_name = 'Project Settings'
    slug = 'incremental_export_logs'

    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    asynchronous = False
    sortable = False

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.select.IncrementalExportFilter',
    ]

    default_datespan_end_date_to_today = True

    @property
    def total_records(self):
        return self._get_checkpoints().count()

    def _get_checkpoints(self):
        checkpoints = IncrementalExportCheckpoint.objects.filter(
            incremental_export__domain=self.domain,
            date_created__range=(self.datespan.startdate, self.datespan.enddate),
        ).order_by('-date_created')

        if self.incremental_export_id:
            checkpoints = checkpoints.filter(
                incremental_export__id=self.incremental_export_id,
            )
        return checkpoints

    @property
    def headers(self):
        columns = [
            DataTablesColumn(ugettext_lazy('Status')),
            DataTablesColumn(ugettext_lazy('Incremenal Export Name')),
            DataTablesColumn(ugettext_lazy('Date')),
            DataTablesColumn(ugettext_lazy('Cases in export')),
            DataTablesColumn(ugettext_lazy('Download File')),
            DataTablesColumn(ugettext_lazy('Request Details')),
        ]
        return DataTablesHeader(*columns)

    @property
    def incremental_export_id(self):
        return self.request.GET.get('incremental_export_id')

    @property
    def rows(self):
        rows = []

        for checkpoint in self._get_paged_checkpoints():
            if checkpoint.status == 1:
                status = f'<span class="label label-success">{ugettext_lazy("Success")}</span>'
            else:
                status = f'<span class="label label-danger">{ugettext_lazy("Failure")}</span>'

            log_url = reverse(MotechLogDetailView.urlname, args=[self.domain, checkpoint.request_log_id])
            file_url = reverse("incremental_export_checkpoint_file", args=[self.domain, checkpoint.id])
            if checkpoint.blob_exists():
                download = (f'<a href="{file_url}"><i class="fa fa-download"></i></a>')
            else:
                download = ugettext_lazy("File Expired")
            rows.append(
                [
                    mark_safe(status),
                    checkpoint.incremental_export.name,
                    checkpoint.date_created.strftime('%Y-%m-%d %H:%M:%S'),
                    checkpoint.doc_count,
                    mark_safe(download),
                    mark_safe(f'<a href="{log_url}">{ugettext_lazy("Request Details")}</a>'),
                ]
            )

        return rows

    def _get_paged_checkpoints(self):
        return self._get_checkpoints()[self.pagination.start:(self.pagination.start + self.pagination.count)]

    @property
    def shared_pagination_GET_params(self):
        params = super(IncrementalExportLogView, self).shared_pagination_GET_params
        params.extend([
            {'name': 'startdate', 'value': self.datespan.startdate.strftime('%Y-%m-%d')},
            {'name': 'enddate', 'value': self.datespan.enddate.strftime('%Y-%m-%d')},
            {'name': 'incremental_export_id', 'value': self.request.GET.get('incremental_export_id')},
        ])
        return params


@require_can_edit_data
def incremental_export_checkpoint_file(request, domain, checkpoint_id):
    try:
        checkpoint = IncrementalExportCheckpoint.objects.get(
            id=checkpoint_id,
            incremental_export__domain=domain
        )
    except IncrementalExportCheckpoint.DoesNotExist:
        return HttpResponseNotFound()

    if not checkpoint.blob_exists():
        return HttpResponseNotFound()
    response = StreamingHttpResponse(FileWrapper(checkpoint.get_blob()), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{checkpoint.filename}"'
    return response
