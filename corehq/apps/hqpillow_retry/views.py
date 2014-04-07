from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.http.response import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop as _
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.hqpillow_retry.filters import PillowFilter, ErrorTypeFilter, DatePropFilter, AttemptsFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from pillow_retry.models import PillowError
from django.conf import settings

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
        'corehq.apps.hqpillow_retry.filters.DatePropFilter',
        'corehq.apps.hqpillow_retry.filters.PillowFilter',
        'corehq.apps.hqpillow_retry.filters.ErrorTypeFilter',
        'corehq.apps.hqpillow_retry.filters.AttemptsFilter',
    )

    report_template_path = 'hqpillow_retry/pillow_errors.html'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Error ID', sortable=False),
            DataTablesColumn('Doc ID', sortable=False),
            DataTablesColumn('Pillow Class', sortable=True),
            DataTablesColumn('Date created', sortable=True),
            DataTablesColumn('Date last attempt', sortable=True),
            DataTablesColumn('Date next attempt', sortable=True),
            DataTablesColumn('Attempts (current / total)', sortable=True),
            DataTablesColumn('Error type', sortable=True),
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
    def sort_field(self):
        sort_fields = [
            'pillow',
            'date_created',
            'date_last_attempt',
            'date_next_attempt',
            'current_attempt',
            'error_type'
        ]
        sort_index = int(self.request.GET.get('iSortCol_0', 2))
        sort_index = 1 if sort_index == 0 else sort_index - 1
        field = sort_fields[sort_index]
        return field if not self.sort_descending else '-{0}'.format(field)

    @property
    def date_field_filter(self):
        return DatePropFilter.get_value(self.request, None)

    @property
    def filter_attempts(self):
        return AttemptsFilter.get_value(self.request, None)

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name=PillowFilter.slug, value=self.pillow),
            dict(name=ErrorTypeFilter.slug, value=self.error),
            dict(name=DatePropFilter.slug, value=self.date_field_filter),
            dict(name=AttemptsFilter.slug, value=str(self.filter_attempts)),
        ]

    @property
    def total_records(self):
        query = self.get_query()
        return query.aggregate(Count('id'))['id__count']

    def get_query(self):
        query = PillowError.objects
        if self.pillow:
            query = query.filter(pillow=self.pillow)
        if self.error:
            query = query.filter(error_type=self.error)
        q = self.date_field_filter + '__gte'
        query = query.filter(**{q: self.datespan.startdate})
        q = self.date_field_filter + '__lte'
        query = query.filter(**{q: self.datespan.enddate_adjusted})
        if self.filter_attempts:
            query = query.filter(current_attempt__gt=settings.PILLOW_RETRY_QUEUE_MAX_PROCESSING_ATTEMPTS)

        return query

    @property
    def rows(self):
        query = self.get_query()
        query = query.order_by(self.sort_field)

        errors = query[self.pagination.start:(self.pagination.start+self.pagination.count)]
        for error in errors:
            msg = error.error_message
            yield [
                self.make_traceback_link(error),
                self.make_search_link(error),
                error.pillow,
                error.date_created,
                error.date_last_attempt,
                error.date_next_attempt,
                '{0} / {1}'.format(error.current_attempt, error.total_attempts),
                error.error_type,
                (msg[:30] + '..') if len(msg) > 32 else msg,
                self.make_checkbox(error)
            ]

    def make_traceback_link(self, error):
        return '<a href="{0}?error={1}" target="_blank">{2}</a>'.format(
            reverse(EditPillowError.urlname),
            error.id,
            error.id
        )

    def make_search_link(self, error):
        return '<a href="{0}?q={1}" target="_blank">{2}...{3}</a>'.format(
            reverse("global_quick_find"),
            error.doc_id,
            error.doc_id[:5],
            error.doc_id[-5:]
        )

    def make_checkbox(self, error):
        return '<input type="checkbox" name="PillowError_{0}" value="1">'.format(error.id)


class EditPillowError(BasePageView):
    urlname = 'pillow_errors'
    page_title = "Pillow Error Details"
    template_name = 'hqpillow_retry/single.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(EditPillowError, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        error_id = self.request.GET.get('error')
        if not error_id:
            return {}

        try:
            error = PillowError.objects.get(id=error_id)
        except PillowError.DoesNotExist:
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
            with transaction.commit_on_success():
                if action == ACTION_DELETE:
                    PillowError.objects.filter(id__in=error_ids).delete()
                elif action == ACTION_RESET:
                    PillowError.objects.filter(id__in=error_ids).update(current_attempt=0, date_next_attempt=datetime.utcnow())

            messages.success(self.request, _("%(num)s records successfully %(action)s") % {'num': len(error_ids), 'action': action})

            if source == SOURCE_SINGLE and action == ACTION_DELETE:
                redirect_url = reverse('admin_report_dispatcher', args=('pillow_errors',))

        redirect_url = redirect_url or request.META.get('HTTP_REFERER', reverse('admin_report_dispatcher', args=('pillow_errors',)))
        return redirect(redirect_url)

