from datetime import datetime
import re
from django.contrib import messages
from django.core.mail import mail_admins
from django.core.mail.message import EmailMessage
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.http.response import Http404
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop as _
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.hqpillow_retry.filters import DatePropFilter, AttemptsFilter, PillowErrorFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base
from pillow_retry.models import PillowError
from django.conf import settings

SOURCE_SINGLE = 'single'
ACTION_RESET = 'reset'
ACTION_DELETE = 'delete'
ACTION_SEND = 'send'
ACTIONS = [ACTION_RESET, ACTION_DELETE, ACTION_SEND]


class PillowErrorsReport(GenericTabularReport, DatespanMixin, GetParamsMixin):
    dispatcher = AdminReportDispatcher
    slug = 'pillow_errors'
    name = _('PillowTop Errors')
    section_name = _("ADMINREPORT")
    asynchronous = False
    ajax_pagination = True
    base_template = 'reports/base_template.html'
    needs_filters = False

    fields = (
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.hqpillow_retry.filters.DatePropFilter',
        'corehq.apps.hqpillow_retry.filters.PillowErrorFilter',
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
            DataTablesColumn('Select', sortable=False),
        )

    @property
    @memoized
    def pillow_error_filter(self):
        return PillowErrorFilter(self.request, None)

    @property
    @memoized
    def pillow_error_vals(self):
        return {item['slug']: item['value'] for item in self.pillow_error_filter.GET_values}

    @property
    def pillow(self):
        return self.pillow_error_vals.get('pillow')

    @property
    def error(self):
        return self.pillow_error_vals.get('error')

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
        return self.pillow_error_filter.shared_pagination_GET_params + [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
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

        if self.date_field_filter:
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
            yield [
                self.make_traceback_link(error),
                self.make_search_link(error),
                error.pillow,
                error.date_created,
                error.date_last_attempt,
                error.date_next_attempt,
                '{0} / {1}'.format(error.current_attempt, error.total_attempts),
                error.error_type,
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

        error_list_url = reverse('admin_report_dispatcher', args=('pillow_errors',))
        if not action or action not in ACTIONS:
            messages.error(self.request, _("Unknown action: '%(action)s'") % {'action': action})
        elif not error_ids:
            messages.error(self.request, _("No error records specified"))
        elif action == ACTION_SEND and not len(error_ids) == 1:
            messages.error(self.request, _("Only one error may be sent to FogBugs at a time."))
        else:
            with transaction.commit_on_success():
                if action == ACTION_DELETE:
                    PillowError.objects.filter(id__in=error_ids).delete()
                elif action == ACTION_RESET:
                    PillowError.objects.filter(id__in=error_ids).\
                        update(current_attempt=0, date_next_attempt=datetime.utcnow())
                elif action == ACTION_SEND:
                    self.bug_report(request.couch_user, error_ids[0])

            success = _("%(num)s records successfully %(action)s") % {'num': len(error_ids), 'action': action}
            messages.success(self.request, success)

            if source == SOURCE_SINGLE and action == ACTION_DELETE:
                redirect_url = error_list_url

        redirect_url = redirect_url or request.META.get('HTTP_REFERER', error_list_url)
        return redirect(redirect_url)

    def bug_report(self, couch_user, error_id):
        error = PillowError.objects.get(id=error_id)

        context = {
            'error': error,
            'url': "{}{}?error={}".format(get_url_base(), reverse(EditPillowError.urlname), error_id)
        }
        message = render_to_string('hqpillow_retry/fb.txt', context)
        subject = 'PillowTop error: {} - {}'.format(error.pillow, error.error_type)

        reply_to = u'"{}" <{}>'.format(couch_user.full_name, couch_user.get_email())
        email = EmailMessage(
            subject=subject,
            body=message,
            to=settings.BUG_REPORT_RECIPIENTS,
            headers={'Reply-To': reply_to}
        )

        # only fake the from email if it's an @dimagi.com account
        if re.search('@dimagi\.com$', couch_user.username):
            email.from_email = couch_user.username
        else:
            email.from_email = settings.CCHQ_BUG_REPORT_EMAIL

        email.send(fail_silently=False)
