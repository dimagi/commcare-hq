from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import re
from django.contrib import messages
from django.core.mail.message import EmailMessage
from django.urls import reverse
from django.db import transaction
from django.db.models.aggregates import Count
from django.http.response import Http404
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop as _
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.hqpillow_retry.filters import PillowErrorFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from memoized import memoized
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import get_url_base
from pillow_retry.models import PillowError
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import naturaltime

SOURCE_SINGLE = 'single'
ACTION_RESET = 'reset'
ACTION_DELETE = 'delete'
ACTION_SEND = 'send'
ACTIONS = [ACTION_RESET, ACTION_DELETE, ACTION_SEND]


def safe_format_date(date):
    return json_format_date(date) if date else date


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
        'corehq.apps.hqpillow_retry.filters.PillowErrorFilter',
    )

    report_template_path = 'hqpillow_retry/pillow_errors.html'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Error', sortable=False),
            DataTablesColumn('Pillow Class', sortable=True),
            DataTablesColumn('Created', sortable=True),
            DataTablesColumn('Next attempt', sortable=True),
            DataTablesColumn('Attempts (current / total)', sortable=True),
            DataTablesColumn('Error type', sortable=True),
            DataTablesColumn('Doc type', sortable=False),
            DataTablesColumn('Domain', sortable=False),
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
            'date_next_attempt',
            'current_attempt',
            'error_type'
        ]
        sort_index = int(self.request.GET.get('iSortCol_0', 2))
        sort_index = 1 if sort_index == 0 else sort_index - 1
        field = sort_fields[sort_index]
        return field if not self.sort_descending else '-{0}'.format(field)

    @property
    def shared_pagination_GET_params(self):
        return self.pillow_error_filter.shared_pagination_GET_params

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

        return query

    @property
    def rows(self):
        query = self.get_query()
        query = query.order_by(self.sort_field)

        next_deploy = _('Next Deploy')
        errors = query[self.pagination.start:(self.pagination.start+self.pagination.count)]
        for error in errors:
            metadata = error.change_metadata or {}
            yield [
                self.make_search_link(error),
                error.pillow.split('.')[-1],
                naturaltime(error.date_created),
                naturaltime(error.date_next_attempt) if error.has_next_attempt() else next_deploy,
                '{0} / {1}'.format(error.current_attempt, error.total_attempts),
                error.error_type,
                metadata.get('document_type'),
                metadata.get('domain'),
                self.make_checkbox(error)
            ]

    def make_search_link(self, error):
        return (
            '{text}<a href="{search_url}?q={doc_id}" target="_blank" title="{search_title}">'
            '<i class="fa fa-search"></i></a>'
            '&nbsp;<a href="{raw_url}?id={doc_id}" target="_blank" title="{raw_title}">'
            '<i class="fa fa-file"></i></a>'
            '&nbsp;<a href="{error_url}?error={error_id}" target="_blank" title="{error_title}">'
            '<i class="fa fa-share"></i></a>'
        ).format(
            text='{}...'.format(error.doc_id[:5]),
            search_url=reverse("global_quick_find"),
            doc_id=error.doc_id,
            search_title=_("Search HQ for this document: %(doc_id)s") % {'doc_id': error.doc_id},
            raw_url=reverse("raw_doc"),
            raw_title=_("Open the raw document: %(doc_id)s") % {'doc_id': error.doc_id},
            error_url=reverse(EditPillowError.urlname),
            error_id=error.id,
            error_title=_("View the details of this error: %(error_id)s") % {'error_id': error.id}
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
            with transaction.atomic():
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

        reply_to = '"{}" <{}>'.format(couch_user.full_name, couch_user.get_email())
        email = EmailMessage(
            subject=subject,
            body=message,
            to=settings.BUG_REPORT_RECIPIENTS,
            headers={'Reply-To': reply_to}
        )

        # only fake the from email if it's an @dimagi.com account
        if re.search(r'@dimagi\.com$', couch_user.username):
            email.from_email = couch_user.username
        else:
            email.from_email = settings.CCHQ_BUG_REPORT_EMAIL

        email.send(fail_silently=False)
