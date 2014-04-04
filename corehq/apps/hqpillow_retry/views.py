from couchdbkit.exceptions import ResourceNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop as _
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.hqpillow_retry.filters import PillowFilter, ErrorTypeFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.couch.bulk import wrapped_docs, CouchTransaction
from pillow_retry.models import PillowError

SOURCE_SINGLE = 'single'
ACTION_RESET = 'reset'
ACTION_DELETE = 'delete'
ACTIONS = [ACTION_RESET, ACTION_DELETE]


class PillowErrorsReport(GenericTabularReport, DatespanMixin, GetParamsMixin):
    dispatcher = AdminReportDispatcher
    slug = 'pillow_errors'
    name = _('PillowTop Errors')
    section_name = _("ADMINREPORT")
    asynchronous = False
    ajax_pagination = True
    base_template = 'reports/base_template.html'

    fields = (
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.hqpillow_retry.filters.PillowFilter',
        'corehq.apps.hqpillow_retry.filters.ErrorTypeFilter',
    )

    report_template_path = 'hqpillow_retry/pillow_errors.html'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Doc ID', sortable=False),
            DataTablesColumn('Pillow Class', sortable=False),
            DataTablesColumn('Date created', sortable=True),
            DataTablesColumn('Date last attempt', sortable=True),
            DataTablesColumn('Date next attempt', sortable=False),
            DataTablesColumn('Attempts (current / total)', sortable=False),
            DataTablesColumn('Error type', sortable=False),
            DataTablesColumn('Error message', sortable=False),
            DataTablesColumn('Select', sortable=False),
        )

    @property
    def pillow(self):
        return PillowFilter.get_value(self.request, None)

    @property
    def error(self):
        return ErrorTypeFilter.get_value(self.request, None)

    @property
    def sort_descending(self):
        return self.request.GET.get('sSortDir_0', 'asc') == 'desc'

    @property
    def by_created(self):
        return self.request.GET.get('iSortCol_0', 2) == 2

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name=PillowFilter.slug, value=self.pillow),
            dict(name=ErrorTypeFilter.slug, value=self.error),
        ]

    @property
    def total_records(self):
        result = PillowError.get_errors(
            pillow=self.pillow,
            error_type=self.error,
            startdate=self.datespan.startdate_param_utc,
            enddate=self.datespan.enddate_param_utc,
            reduce=True,
            by_date_created=self.by_created
        ).one()
        return result['value']['count'] if result else 0

    @property
    def rows(self):
        errors = PillowError.get_errors(
            pillow=self.pillow,
            error_type=self.error,
            startdate=self.datespan.startdate_param_utc,
            enddate=self.datespan.enddate_param_utc,
            limit=self.pagination.count,
            skip=self.pagination.start,
            include_docs=True,
            by_date_created=self.by_created,
            descending=self.sort_descending
        )

        for error in errors:
            yield [
                self.make_traceback_link(error),
                error.pillow,
                error.date_created,
                error.date_last_attempt,
                error.date_next_attempt,
                '{0} / {1}'.format(error.current_attempt, error.total_attempts),
                error.error_type,
                error.error_message,
                self.make_checkbox(error)
            ]

    def make_traceback_link(self, error):
        return '<a href="{0}?error={1}" target="_blank">{2}</a>'.format(
            reverse(EditPillowError.urlname),
            error.get_id,
            error.doc_id
        )

    def make_checkbox(self, error):
        return '<input type="checkbox" name="PillowError_{0}" value="1">'.format(error.get_id)


class EditPillowError(BasePageView):
    urlname = 'pillow_errors'
    page_title = "Pillow Error Details"
    template_name = 'pillow_retry/single.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(EditPillowError, self).dispatch(request, *args, **kwargs)


    @property
    def page_context(self):
        error_id = self.request.GET.get('error')
        if not error_id:
            return {}

        try:
            error = PillowError.get(error_id)
        except ResourceNotFound:
            raise Http404

        return {
            'error': error
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        source = request.POST.get('source')
        error_ids = []
        prefix = 'PillowError_'
        prefix_len = len(prefix)
        for p in request.POST:
            if p.startswith(prefix):
                error_ids.append(p[prefix_len:])

        redirect_url = None

        if not action or action not in ACTIONS:
            messages.error(self.request, _("Unknown action: '%(action)s'") % {'action': action})
        elif not error_ids:
            messages.error(self.request, _("No error records specified"))
        else:
            error_docs = wrapped_docs(PillowError, error_ids)
            with CouchTransaction() as transaction:
                if action == ACTION_DELETE:
                    transaction.delete_all(error_docs)
                elif action == ACTION_RESET:
                    for doc in error_docs:
                        doc.reset_attempts()
                        transaction.save(doc)

            messages.success(self.request, _("%(num)s records successfully %(action)s") % {'num': len(error_ids), 'action': action})

            if source == SOURCE_SINGLE and action == ACTION_DELETE:
                redirect_url = reverse('admin_report_dispatcher', args=('pillow_errors',))

        redirect_url = redirect_url or request.META.get('HTTP_REFERER', reverse('admin_report_dispatcher', args=('pillow_errors',)))
        return redirect(redirect_url)

