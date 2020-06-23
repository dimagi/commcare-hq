from wsgiref.util import FileWrapper

from django.contrib import messages
from django.http import HttpResponseNotFound, StreamingHttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from corehq.apps.data_interfaces.dispatcher import require_can_edit_data
from corehq.apps.export.forms import (
    IncrementalExportForm,
    UpdateIncrementalExportForm,
)
from corehq.apps.export.models.incremental import (
    IncrementalExport,
    IncrementalExportCheckpoint,
    generate_and_send_incremental_export,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.settings.views import BaseProjectDataView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.motech.views import MotechLogDetailView
from corehq.toggles import INCREMENTAL_EXPORTS


@method_decorator(INCREMENTAL_EXPORTS.required_decorator(), name="dispatch")
class IncrementalExportView(BaseProjectDataView, CRUDPaginatedViewMixin):
    page_title = _("Incremental Export")
    urlname = "incremental_export_view"

    template_name = "export/incremental_export.html"

    @property
    def total(self):
        # How many documents are you paginating through?
        return self.base_query.count()

    @property
    def base_query(self):
        return IncrementalExport.objects.filter(domain=self.domain)

    @property
    def column_names(self):
        return [
            _("Active"),
            _("Name"),
            _("Case Data Export"),
            _("Connection Settings"),
            _("Edit"),
            _("Delete"),
            _("Resend all cases")
        ]

    @property
    def page_context(self):
        context = self.pagination_context
        return context

    @property
    def paginated_list(self):
        for incremental_export in self.base_query.all():
            yield {
                "itemData": self._item_data(incremental_export),
                "template": "base-incremental-export-template",
            }

    def _item_data(self, incremental_export):
        return {
            "id": incremental_export.id,
            "active": incremental_export.active,
            "name": incremental_export.name,
            "export_instance": incremental_export.export_instance.name,
            "connection_settings": incremental_export.connection_settings.name,
            "updateForm": self.get_update_form_response(
                self.get_update_form(instance=incremental_export)
            ),
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def get_deleted_item_data(self, item_id):
        deleted_export = IncrementalExport.objects.get(id=item_id, domain=self.domain)
        deleted_export.delete()
        return {
            "itemData": self._item_data(deleted_export),
            "template": "deleted-incremental-export-template",
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == "POST" and not is_blank:
            return IncrementalExportForm(self.request, self.request.POST)
        return IncrementalExportForm(self.request)

    create_item_form_class = "form form-horizontal"

    def get_create_item_data(self, create_form):
        new_item = create_form.save()
        return {
            "itemData": self._item_data(new_item),
            "template": "base-incremental-export-template",
        }

    def get_update_form(self, instance=None):
        if instance is None:
            instance = IncrementalExport.objects.get(
                id=self.request.POST.get("id"), domain=self.domain
            )
        if self.request.method == "POST" and self.action == "update":
            return UpdateIncrementalExportForm(self.request, self.request.POST, instance=instance)
        return UpdateIncrementalExportForm(self.request, instance=instance)

    def get_updated_item_data(self, update_form):
        item = update_form.save()
        return {
            "itemData": self._item_data(item),
            "template": "base-incremental-export-template",
        }


class IncrementalExportLogView(GenericTabularReport, DatespanMixin):
    name = "Incremental Export Logs"
    base_template = "reports/base_template.html"
    section_name = "Project Settings"
    slug = "incremental_export_logs"

    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    asynchronous = False
    sortable = False

    fields = [
        "corehq.apps.reports.filters.dates.DatespanFilter",
        "corehq.apps.reports.filters.select.IncrementalExportFilter",
    ]

    default_datespan_end_date_to_today = True

    @property
    def total_records(self):
        return self._get_checkpoints().count()

    def _get_checkpoints(self):
        checkpoints = IncrementalExportCheckpoint.objects.filter(
            incremental_export__domain=self.domain,
            date_created__range=(self.datespan.startdate_param_utc, self.datespan.enddate_param_utc),
        ).order_by("-date_created")

        if self.incremental_export_id:
            checkpoints = checkpoints.filter(incremental_export__id=self.incremental_export_id,)
        return checkpoints

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_("Status")),
            DataTablesColumn(_("Incremenal Export Name")),
            DataTablesColumn(_("Date")),
            DataTablesColumn(_("Cases in export")),
            DataTablesColumn(_("Download File")),
            DataTablesColumn(_("Request Details")),
            DataTablesColumn(_("Resend all cases")),
        ]
        return DataTablesHeader(*columns)

    @property
    def incremental_export_id(self):
        return self.request.GET.get("incremental_export_id")

    @property
    def rows(self):
        rows = []

        for checkpoint in self._get_paged_checkpoints():
            if checkpoint.status == 1:
                status = f'<span class="label label-success">{_("Success")}</span>'
            else:
                status = f'<span class="label label-danger">{_("Failure")}</span>'

            log_url = reverse(MotechLogDetailView.urlname, args=[self.domain, checkpoint.request_log_id])
            file_url = reverse("incremental_export_checkpoint_file", args=[self.domain, checkpoint.id])
            reset_url = reverse("incremental_export_reset_checkpoint", args=[self.domain, checkpoint.id])
            if checkpoint.blob_exists():
                download = f'<a href="{file_url}"><i class="fa fa-download"></i></a>'
            else:
                download = _("File Expired")
            rows.append(
                [
                    mark_safe(status),
                    checkpoint.incremental_export.name,
                    checkpoint.date_created.strftime("%Y-%m-%d %H:%M:%S"),
                    checkpoint.doc_count,
                    mark_safe(download),
                    mark_safe(f'<a href="{log_url}">{_("Request Details")}</a>'),
                    mark_safe(
                        f'<a href="{reset_url}">{_("Resend all cases after this checkpoint")}</a>'
                    ),
                ]
            )

        return rows

    def _get_paged_checkpoints(self):
        return self._get_checkpoints()[
            self.pagination.start: (self.pagination.start + self.pagination.count)
        ]

    @property
    def shared_pagination_GET_params(self):
        params = super(IncrementalExportLogView, self).shared_pagination_GET_params
        params.extend(
            [
                {"name": "startdate", "value": self.datespan.startdate.strftime("%Y-%m-%d")},
                {"name": "enddate", "value": self.datespan.enddate.strftime("%Y-%m-%d")},
                {
                    "name": "incremental_export_id",
                    "value": self.request.GET.get("incremental_export_id"),
                },
            ]
        )
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


@require_can_edit_data
def incremental_export_reset_checkpoint(request, domain, checkpoint_id):
    """Resend all cases after a particular checkpoint
    """
    try:
        checkpoint = IncrementalExportCheckpoint.objects.get(
            id=checkpoint_id,
            incremental_export__domain=domain
        )
    except IncrementalExportCheckpoint.DoesNotExist:
        return HttpResponseNotFound()

    incremental_export = checkpoint.incremental_export
    date = checkpoint.last_doc_date

    new_checkpoint = generate_and_send_incremental_export(incremental_export, date)
    doc_count = new_checkpoint.doc_count if new_checkpoint else 0
    messages.success(
        request, _(
            f"{doc_count} cases modified after {date.strftime('%Y-%m-%d %H:%M:%S')} have been resent"
        )
    )

    return HttpResponseRedirect(
        reverse('domain_report_dispatcher', args=[domain, IncrementalExportLogView.slug])
    )


@require_can_edit_data
def incremental_export_resend_all(request, domain, incremental_export_id):
    try:
        incremental_export = IncrementalExport.objects.get(id=incremental_export_id, domain=domain)
    except IncrementalExport.DoesNotExist:
        return HttpResponseNotFound()

    new_checkpoint = generate_and_send_incremental_export(incremental_export, from_date=None)
    doc_count = new_checkpoint.doc_count if new_checkpoint else 0
    messages.success(
        request, _(
            f"{doc_count} cases have been resent for export '{incremental_export.name}'"
        )
    )
    url = "{}?{}".format(
        reverse('domain_report_dispatcher', args=[domain, IncrementalExportLogView.slug]),
        "incremental_export_id={}".format(incremental_export_id)
    )
    return HttpResponseRedirect(url)
