import copy
import io
import json
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import cmp_to_key, partial

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.html import format_html, format_html_join
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)
from django.views.generic.edit import ModelFormMixin, ProcessFormView
from django.views.generic import View
from django.views.generic.base import TemplateView

import csv
import pytz
from couchdbkit.exceptions import ResourceNotFound
from django_prbac.utils import has_privilege
from memoized import memoized

from casexml.apps.case import const
from casexml.apps.case.cleanup import close_case, rebuild_case_from_forms
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.templatetags.case_tags import case_inline_display
from casexml.apps.case.util import (
    get_case_history,
    get_paged_changes_to_case_property,
)
from casexml.apps.case.views import get_wrapped_case
from casexml.apps.case.xform import extract_case_blocks, get_case_updates
from casexml.apps.case.xml import V2
from couchexport.export import Format, export_from_tables
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_response

import langcodes
from corehq import privileges, toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.const import USERCASE_ID, USERCASE_TYPE
from corehq.apps.app_manager.dbaccessors import get_latest_app_ids_and_versions
from corehq.apps.app_manager.models import Application, ShadowForm
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesHelper
from corehq.apps.app_manager.util import get_form_source_download_url
from corehq.apps.cloudcare import CLOUDCARE_DEVICE_ID
from corehq.apps.cloudcare.const import DEVICE_ID as FORMPLAYER_DEVICE_ID
from corehq.apps.cloudcare.touchforms_api import (
    get_user_contributions_to_touchforms_session,
)
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest,
)
from corehq.apps.domain.models import Domain, DomainAuditRecordEntry
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.export.const import KNOWN_CASE_PROPERTIES
from corehq.apps.export.models import CaseExportDataSchema
from corehq.apps.export.utils import is_occurrence_deleted
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import (
    EDIT_FORM_XMLNS,
    resave_case,
    submit_case_blocks,
)
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_jquery_ui,
    use_multiselect,
)
from corehq.apps.hqwebapp.doc_info import DocInfo, get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.locations.permissions import (
    can_edit_form_location,
    conditionally_location_safe,
    location_restricted_exception,
    location_safe,
    report_class_is_location_safe,
    user_can_access_case,
)
from corehq.apps.products.models import SQLProduct
from corehq.apps.receiverwrapper.auth import AuthContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.exceptions import EditFormValidationError
from corehq.apps.reports.formdetails.readable import (
    get_data_cleaning_data,
    get_readable_data_for_submission,
)
from corehq.apps.reports.util import validate_xform_for_edit
from corehq.apps.reports.view_helpers import case_hierarchy_context
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.saved_reports.tasks import (
    send_delayed_report,
    send_email_report,
)
from corehq.apps.userreports.util import \
    default_language as ucr_default_language
from corehq.apps.users.dbaccessors import get_all_user_rows
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Permissions,
    WebUser,
)
from corehq.apps.users.permissions import (
    CASE_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    FORM_EXPORT_PERMISSION,
)
from corehq.blobs import CODES, NotFound, get_blob_db, models
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
    LedgerAccessors,
)
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import UserRequestedRebuild
from corehq.form_processor.utils.general import use_sqlite_backend
from corehq.form_processor.utils.xform import resave_form
from corehq.motech.repeaters.dbaccessors import (
    get_repeat_records_by_payload_id,
)
from corehq.tabs.tabclasses import ProjectReportsTab
from corehq.util.couch import get_document_or_404
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import (
    get_timezone_for_request,
    get_timezone_for_user,
)
from corehq.util import cmp
from corehq.util.view_utils import (
    absolute_reverse,
    get_case_or_404,
    get_form_or_404,
    request_as_dict,
    reverse,
)
from no_exceptions.exceptions import Http403

from .dispatcher import ProjectReportDispatcher
from .forms import SavedReportConfigForm, TableauServerForm, TableauVisualizationForm
from .lookup import ReportLookup, get_full_report_name
from .models import TableauVisualization, TableauServer
from .standard import ProjectReport, inspect
from .standard.cases.basic import CaseListReport

# Number of columns in case property history popup
DYNAMIC_CASE_PROPERTIES_COLUMNS = 4


datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

require_form_export_permission = require_permission(
    Permissions.view_report, FORM_EXPORT_PERMISSION, login_decorator=None)
require_form_deid_export_permission = require_permission(
    Permissions.view_report, DEID_EXPORT_PERMISSION, login_decorator=None)
require_case_export_permission = require_permission(
    Permissions.view_report, CASE_EXPORT_PERMISSION, login_decorator=None)

require_form_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.inspect.SubmitHistory', login_decorator=None)
require_case_view_permission = require_permission(Permissions.view_report, 'corehq.apps.reports.standard.cases.basic.CaseListReport', login_decorator=None)

require_can_view_all_reports = require_permission(Permissions.view_reports)


def can_view_attachments(request):
    return (
        request.couch_user.has_permission(
            request.domain, 'view_report',
            data='corehq.apps.reports.standard.cases.basic.CaseListReport'
        )
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.user.username)
        or toggles.ALLOW_CASE_ATTACHMENTS_VIEW.enabled(request.domain)
    )


class BaseProjectReportSectionView(BaseDomainView):
    section_name = ugettext_lazy("Project Reports")

    def dispatch(self, request, *args, **kwargs):
        request.project = Domain.get_by_name(self.domain)
        if not hasattr(request, 'couch_user'):
            raise Http404()
        if not user_can_view_reports(request.project, request.couch_user):
            raise Http404()
        return super(BaseProjectReportSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse('reports_home', args=(self.domain, ))


@location_safe
class MySavedReportsView(BaseProjectReportSectionView):
    urlname = 'saved_reports'
    page_title = ugettext_noop("My Saved Reports")
    template_name = 'reports/reports_home.html'

    @use_jquery_ui
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(MySavedReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def language(self):
        return self.request.couch_user.language or ucr_default_language()

    @property
    def good_configs(self):
        all_configs = ReportConfig.by_domain_and_owner(self.domain, self.request.couch_user._id)
        good_configs = []
        for config in all_configs:
            if config.is_configurable_report and not config.configurable_report:
                continue

            good_configs.append(config.to_complete_json(lang=self.language))
        return good_configs

    @property
    def scheduled_reports(self):

        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        scheduled_reports = [
            r for r in ReportNotification.by_domain_and_owner(
                self.domain, self.request.couch_user._id)
            if _is_valid(r)
        ]
        scheduled_reports = sorted(scheduled_reports,
                                   key=lambda s: s.configs[0].name)
        for report in scheduled_reports:
            self._adjust_report_day_and_time(report)
        return sorted(scheduled_reports, key=self._report_sort_key())

    @property
    def others_scheduled_reports(self):
        def _is_valid(rn):
            # the _id check is for weird bugs we've seen in the wild that look like
            # oddities in couch.
            return (
                hasattr(rn, "_id")
                and rn._id
                and rn.configs
                and (
                    not hasattr(rn, 'report_slug')
                    or rn.report_slug != 'admin_domains'
                )
            )

        ret = []
        key = [self.domain]
        all_scheduled_reports = ReportNotification.view('reportconfig/user_notifications', reduce=False,
                                                        include_docs=True, startkey=key, endkey=key + [{}])
        user = self.request.couch_user
        user_email = user.get_email()
        for scheduled_report in all_scheduled_reports:
            if not _is_valid(scheduled_report) or user_email == scheduled_report.owner_email:
                continue
            self._adjust_report_day_and_time(scheduled_report)
            if scheduled_report.can_be_viewed_by(user):
                ret.append(scheduled_report)
        return sorted(ret, key=self._report_sort_key())

    def _report_sort_key(self):
        return lambda report: report.configs[0].full_name.lower() if report.configs else None

    def _adjust_report_day_and_time(self, report):
        time_difference = get_timezone_difference(self.domain)
        (report.hour, day_change) = recalculate_hour(
            report.hour,
            int(time_difference[:3]),
            int(time_difference[3:])
        )
        report.minute = 0
        if day_change:
            report.day = calculate_day(report.interval, report.day, day_change)
        return report

    @property
    def page_context(self):
        user = self.request.couch_user
        others_scheduled_reports = self.others_scheduled_reports

        class OthersScheduledReportWrapper(ReportNotification):
            @property
            def context_secret(self):
                return self.get_secret(user.get_email())

        for other_report in others_scheduled_reports:
            other_report.__class__ = OthersScheduledReportWrapper

        others_scheduled_reports = [
            self.report_details(r, user.get_email(), r.context_secret) for r in others_scheduled_reports
        ]

        scheduled_reports = [
            self.report_details(r) for r in self.scheduled_reports
        ]

        return {
            'couch_user': user,
            'user_email': user.get_email(),
            'is_admin': user.is_domain_admin(self.domain),
            'configs': self.good_configs,
            'scheduled_reports': scheduled_reports,
            'others_scheduled_reports': others_scheduled_reports,
            'report': {
                'title': self.page_title,
                'show': True,
                'slug': None,
                'is_async': True,
                'section_name': self.section_name,
            }
        }

    @staticmethod
    def report_details(report, user_email=None, context_secret=None):
        details = {
            'id': report.get_id,
            'addedToBulk': report.addedToBulk,
            'domain': report.domain,
            'owner_id': report.owner_id,
            'recipient_emails': report.recipient_emails,
            'config_ids': report.config_ids,
            'send_to_owner': report.send_to_owner,
            'hour': report.hour,
            'minute': report.minute,
            'day': report.day,
            'uuid': report.uuid,
            'start_date': report.start_date,

            #property methods
            'configs': [{'url': r.url,
                         'name': r.name,
                         'report_name': r.report_name} for r in report.configs],
            'is_editable': report.is_editable,
            'owner_email': report.owner_email,
            'day_name': report.day_name,

            #urls
            'editUrl': reverse(ScheduledReportsView.urlname, args=(report.domain, report.get_id)),
            'viewUrl': reverse(view_scheduled_report, args=(report.domain, report.get_id)),
            'sendUrl': reverse(send_test_scheduled_report, args=(report.domain, report.get_id)),
            'deleteUrl': reverse(delete_scheduled_report, args=(report.domain, report.get_id)),
        }

        #only for others_scheduled_reports
        if user_email and context_secret:
            details['unsubscribeUrl'] = reverse(ReportNotificationUnsubscribeView.urlname,
                                                args=(report.get_id, user_email, context_secret))

        return details


def should_update_export(last_accessed):
    cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    return not last_accessed or last_accessed < cutoff


def touch_saved_reports_views(user, domain):
    """
    Hit the saved reports views so stale=update_after doesn't cause the user to
    see old or deleted data after a change when they next load the reports
    homepage.

    """
    ReportConfig.by_domain_and_owner(domain, user._id, limit=1, stale=False)
    ReportNotification.by_domain_and_owner(domain, user._id, limit=1, stale=False)


@location_safe
class AddSavedReportConfigView(View):
    name = 'add_report_config'

    @method_decorator(login_and_domain_required)
    def post(self, request, domain, *args, **kwargs):
        self.domain = domain

        if not self.saved_report_config_form.is_valid():
            errors = self.saved_report_config_form.errors.get('__all__', [])
            return HttpResponseBadRequest(', '.join(errors))

        update_config_data = copy.copy(self.saved_report_config_form.cleaned_data)
        del update_config_data['_id']
        update_config_data.update({
            'filters': self.filters,
        })
        for field in self.config.properties().keys():
            if field in update_config_data:
                setattr(self.config, field, update_config_data[field])

        # remove start and end date if the date range is "last xx days" or none
        if self.saved_report_config_form.cleaned_data['date_range'] in [
            'last30',
            'last7',
            'lastn',
            'lastmonth',
            'lastyear',
            None,
        ]:
            if "start_date" in self.config:
                delattr(self.config, "start_date")
            if "end_date" in self.config:
                delattr(self.config, "end_date")
        # remove days if the date range has specific dates
        elif self.saved_report_config_form.cleaned_data['date_range'] in [
            'since',
            'range',
        ]:
            if "days" in self.config:
                delattr(self.config, "days")

        self.config.save()
        ProjectReportsTab.clear_dropdown_cache(self.domain, request.couch_user)
        touch_saved_reports_views(request.couch_user, self.domain)

        return json_response(self.config)

    @property
    @memoized
    def config(self):
        _id = self.saved_report_config_form.cleaned_data['_id']
        if not _id:
            _id = None  # make sure we pass None not a blank string
        config = ReportConfig.get_or_create(_id)
        if config.owner_id:
            # in case a user maliciously tries to edit another user's config
            assert config.owner_id == self.user_id
        else:
            config.domain = self.domain
            config.owner_id = self.user_id
        return config

    @property
    @memoized
    def saved_report_config_form(self):
        return SavedReportConfigForm(
            self.domain,
            self.user_id,
            self.post_data
        )

    @property
    def filters(self):
        filters = copy.copy(self.post_data.get('filters', {}))
        for field in ['startdate', 'enddate']:
            if field in filters:
                del filters[field]
        return filters

    @property
    def post_data(self):
        return json.loads(self.request.body.decode('utf-8'))

    @property
    def user_id(self):
        return self.request.couch_user._id

@login_and_domain_required
@datespan_default
def email_report(request, domain, report_slug, dispatcher_class=ProjectReportDispatcher, once=False):
    from .forms import EmailReportForm

    form = EmailReportForm(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    if not _can_email_report(report_slug, request, dispatcher_class, domain):
        raise Http404()

    recipient_emails = set(form.cleaned_data['recipient_emails'])
    if form.cleaned_data['send_to_owner']:
        recipient_emails.add(request.couch_user.get_email())

    request_data = request_as_dict(request)

    report_type = dispatcher_class.prefix
    send_email_report.delay(recipient_emails, domain, report_slug, report_type,
                            request_data, once, form.cleaned_data)
    return HttpResponse()


def _can_email_report(report_slug, request, dispatcher_class, domain):
    dispatcher = dispatcher_class()
    lookup = ReportLookup(dispatcher.map_name)
    report = lookup.get_report(domain, report_slug)
    if not report:
        return False

    report_name = get_full_report_name(report)
    return dispatcher.permissions_check(report_name, request, domain)


@login_and_domain_required
@require_http_methods(['DELETE'])
def delete_config(request, domain, config_id):
    try:
        saved_report = ReportConfig.get(config_id)
    except ResourceNotFound:
        raise Http404()

    if not _can_delete_saved_report(saved_report, request.couch_user, domain):
        raise Http404()

    saved_report.delete()
    ProjectReportsTab.clear_dropdown_cache(domain, request.couch_user)

    touch_saved_reports_views(request.couch_user, domain)
    return HttpResponse()


def _can_delete_saved_report(report, user, domain):
    return domain == report.domain and user._id == report.owner_id


def normalize_hour(hour):
    day_change = 0
    if hour < 0:
        day_change = -1
        hour += 24
    elif hour >= 24:
        day_change = 1
        hour -= 24

    assert 0 <= hour < 24
    return (hour, day_change)


def calculate_hour(hour, hour_difference, minute_difference):
    hour -= hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour -= 1
    return normalize_hour(hour)


def recalculate_hour(hour, hour_difference, minute_difference):
    hour += hour_difference
    if hour_difference > 0 and minute_difference != 0:
        hour += 1
    return normalize_hour(hour)


def get_timezone_difference(domain):
    return datetime.now(pytz.timezone(Domain.get_by_name(domain)['default_timezone'])).strftime('%z')


def calculate_day(interval, day, day_change):
    if interval == "weekly":
        return (day + day_change) % 7
    elif interval == "monthly":
        return (day - 1 + day_change) % 31 + 1
    return day


class ScheduledReportsView(BaseProjectReportSectionView):
    urlname = 'edit_scheduled_report'
    page_title = _("Scheduled Report")
    template_name = 'reports/edit_scheduled_report.html'

    @method_decorator(require_permission(Permissions.download_reports))
    @use_multiselect
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(ScheduledReportsView, self).dispatch(request, *args, **kwargs)

    @property
    def scheduled_report_id(self):
        return self.kwargs.get('scheduled_report_id')

    def can_edit_report(self, report_instance):
        owner = report_instance.owner
        owner_domain = report_instance.domain
        current_user = self.request.couch_user
        return current_user.user_id == owner.user_id or current_user.is_domain_admin(owner_domain)

    @property
    @memoized
    def report_notification(self):
        if self.scheduled_report_id:
            instance = ReportNotification.get(self.scheduled_report_id)
            time_difference = get_timezone_difference(self.domain)
            (instance.hour, day_change) = recalculate_hour(
                instance.hour,
                int(time_difference[:3]),
                int(time_difference[3:])
            )
            instance.minute = 0
            if day_change:
                instance.day = calculate_day(instance.interval, instance.day, day_change)

            if not self.can_edit_report(instance):
                raise Http403()
        else:
            instance = ReportNotification(
                owner_id=self.request.couch_user._id,
                domain=self.domain,
                config_ids=[],
                hour=8,
                minute=0,
                send_to_owner=True,
                recipient_emails=[],
                language=None,
            )
        return instance

    @property
    def is_new(self):
        """True if before this request the ReportNotification object did not exist"""
        return bool(not self.scheduled_report_id)

    @property
    def page_name(self):
        if not self.configs:
            return self.page_title
        if self.is_new:
            return _("New Scheduled Report")
        return _("Edit Scheduled Report")

    @property
    def owner_id(self):
        if self.scheduled_report_id:
            return ReportNotification.get(self.scheduled_report_id).owner_id
        else:
            return None

    @property
    @memoized
    def configs(self):
        user = self.request.couch_user
        if (self.scheduled_report_id and user.is_domain_admin(self.domain) and
                user._id != self.owner_id):
            return self.report_notification.configs
        return [
            c for c in ReportConfig.by_domain_and_owner(self.domain, user._id)
            if c.report and c.report.emailable
        ]

    @property
    def config_choices(self):
        config_choices = [(c._id, c.full_name) for c in self.configs]

        def _sort_key(config_choice):
            config_choice_id = config_choice[0]
            if config_choice_id in self.report_notification.config_ids:
                return self.report_notification.config_ids.index(config_choice_id)
            else:
                return len(self.report_notification.config_ids)

        return sorted(config_choices, key=_sort_key)

    @property
    @memoized
    def scheduled_report_form(self):
        initial = self.report_notification.to_json()
        kwargs = {'initial': initial}
        if self.request.method == "POST":
            args = (self.request.POST, )
            selected_emails = self.request.POST.getlist('recipient_emails', {})
        else:
            args = ()
            selected_emails = kwargs.get('initial', {}).get('recipient_emails', [])

        web_user_emails = [
            WebUser.wrap(row['doc']).get_email()
            for row in get_all_user_rows(self.domain, include_web_users=True,
                                         include_mobile_users=False, include_docs=True)
        ]
        for email in selected_emails:
            if email not in web_user_emails:
                web_user_emails = [email] + web_user_emails

        from corehq.apps.reports.forms import ScheduledReportForm
        form = ScheduledReportForm(*args, **kwargs)
        form.fields['config_ids'].choices = self.config_choices
        form.fields['recipient_emails'].choices = [(e, e) for e in web_user_emails]

        form.fields['hour'].help_text = "This scheduled report's timezone is %s (%s GMT)" % \
                                        (Domain.get_by_name(self.domain)['default_timezone'],
                                        get_timezone_difference(self.domain)[:3] + ':'
                                        + get_timezone_difference(self.domain)[3:])
        return form

    @property
    def page_context(self):
        context = {
            'form': None,
            'report': {
                'show': user_can_view_reports(self.request.project, self.request.couch_user),
                'slug': None,
                'default_url': reverse('reports_home', args=(self.domain,)) + '#scheduled-reports',
                'is_async': False,
                'section_name': ProjectReport.section_name,
                'title': self.page_name,
            }
        }

        if not self.configs and not self.request.couch_user.is_domain_admin(self.domain):
            return context

        is_configurable_map = {c._id: c.is_configurable_report for c in self.configs}
        supports_translations = {c._id: c.supports_translations for c in self.configs}
        languages_map = {c._id: list(c.languages | set(['en'])) for c in self.configs}
        languages_for_select = {tup[0]: tup for tup in langcodes.get_all_langs_for_select()}

        context.update({
            'form': self.scheduled_report_form,
            'day_value': getattr(self.report_notification, "day", 1),
            'weekly_day_options': ReportNotification.day_choices(),
            'monthly_day_options': [(i, i) for i in range(1, 32)],
            'form_action': _("Create a new") if self.is_new else _("Edit"),
            'is_configurable_map': is_configurable_map,
            'supports_translations': supports_translations,
            'languages_map': languages_map,
            'languages_for_select': languages_for_select,
            'is_owner': self.is_new or self.request.couch_user._id == self.owner_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        if self.scheduled_report_form.is_valid():
            try:
                self.report_notification.update_attributes(list(self.scheduled_report_form.cleaned_data.items()))
            except ValidationError as err:
                kwargs['error'] = str(err)
                messages.error(request, ugettext_lazy(kwargs['error']))
                return self.get(request, *args, **kwargs)
            time_difference = get_timezone_difference(self.domain)
            (self.report_notification.hour, day_change) = calculate_hour(
                self.report_notification.hour, int(time_difference[:3]), int(time_difference[3:])
            )
            self.report_notification.minute = int(time_difference[3:])
            if day_change:
                self.report_notification.day = calculate_day(
                    self.report_notification.interval,
                    self.report_notification.day,
                    day_change
                )

            self.report_notification.save()
            ProjectReportsTab.clear_dropdown_cache(self.domain, self.request.couch_user)
            if self.is_new:
                DomainAuditRecordEntry.update_calculations(self.domain, 'cp_n_saved_scheduled_reports')
                messages.success(request, _("Scheduled report added."))
            else:
                messages.success(request, _("Scheduled report updated."))

            touch_saved_reports_views(request.couch_user, self.domain)
            return HttpResponseRedirect(reverse('reports_home', args=(self.domain,)) + '#scheduled-reports')

        return self.get(request, *args, **kwargs)


class ReportNotificationUnsubscribeView(TemplateView):
    template_name = 'reports/notification_unsubscribe.html'
    urlname = 'notification_unsubscribe'
    not_found_error = ugettext_noop('Could not find the requested Scheduled Report')
    broken_link_error = ugettext_noop('Invalid unsubscribe link')
    report = None

    def get(self, request, *args, **kwargs):
        if 'success' not in kwargs and 'error' not in kwargs:
            try:
                self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
                email = kwargs.pop('user_email')

                if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                    raise ValidationError(self.broken_link_error)
                if email not in self.report.all_recipient_emails:
                    raise ValidationError(ugettext_noop('This email address has already been unsubscribed.'))
            except ResourceNotFound:
                kwargs['error'] = self.not_found_error
            except ValidationError as err:
                kwargs['error'] = err.message

        if 'error' in kwargs:
            messages.error(request, ugettext_lazy(kwargs['error']))
        elif 'success' in kwargs:
            messages.success(request, ugettext_lazy(kwargs['success']))

        return super(ReportNotificationUnsubscribeView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReportNotificationUnsubscribeView, self).get_context_data(**kwargs)
        context.update({'report': self.report})
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.report = ReportNotification.get(kwargs.pop('scheduled_report_id'))
            email = kwargs.pop('user_email')

            if kwargs.pop('scheduled_report_secret') != self.report.get_secret(email):
                raise ValidationError(self.broken_link_error)

            self.report.remove_recipient(email)

            if len(self.report.recipient_emails) > 0 or self.report.send_to_owner:
                self.report.save()
            else:
                self.report.delete()

            kwargs['success'] = ugettext_noop('Successfully unsubscribed from report notification.')
        except ResourceNotFound:
            kwargs['error'] = self.not_found_error
        except ValidationError as err:
            kwargs['error'] = err.message

        return self.get(request, *args, **kwargs)


@login_and_domain_required
@require_POST
def delete_scheduled_report(request, domain, scheduled_report_id):
    user = request.couch_user
    delete_count = request.POST.get("bulk_delete_count")

    try:
        if delete_count:
            delete_list = json.loads(request.POST.get("deleteList"))
            scheduled_reports = [ReportNotification.get(report_id) for report_id in delete_list]
        else:
            scheduled_report = ReportNotification.get(scheduled_report_id)
    except ResourceNotFound:
        # was probably already deleted by a fast-clicker.
        pass
    else:
        if delete_count:
            for report in scheduled_reports:
                if not _can_delete_scheduled_report(report, user, domain):
                    raise Http404()

            for report in scheduled_reports:
                report.delete()
            if int(delete_count) > 1:
                plural = "s were"
            else:
                plural = " was"
            messages.success(
                request,
                format_html(_("<strong>{}</strong> Scheduled report{} deleted!"), delete_count, plural)
            )
            # not necessary since it just refreshes from the js
            return HttpResponse(reverse("reports_home", args=(domain,)) + '#scheduled-reports')
        else:
            if not _can_delete_scheduled_report(scheduled_report, user, domain):
                raise Http404()

            scheduled_report.delete()
            messages.success(request, "Scheduled report deleted!")

    return HttpResponseRedirect(reverse("reports_home", args=(domain,)) + '#scheduled-reports')


def _can_delete_scheduled_report(report, user, domain):
    if report.domain != domain:
        return False

    return user._id == report.owner_id or user.is_domain_admin(domain)


@login_and_domain_required
def send_test_scheduled_report(request, domain, scheduled_report_id):
    if not _can_send_test_report(scheduled_report_id, request.couch_user, domain):
        raise Http404()
    send_count = request.POST.get("bulk_send_count")

    try:
        if send_count:
            for report_id in json.loads(request.POST.get("sendList")):
                send_delayed_report(report_id)
        else:
            send_delayed_report(scheduled_report_id)
    except Exception as e:
        import logging
        logging.exception(e)
        messages.error(request, _("An error occurred, message unable to send"))
    else:
        if send_count and int(send_count) > 1:
            messages.success(
                request,
                format_html(_("{} reports sent to their recipients"), send_count)
            )
        else:
            messages.success(request, _("Report sent to this report's recipients"))

    if send_count:
        return HttpResponse(reverse("reports_home", args=(domain,)) + '#scheduled-reports')
    else:
        return HttpResponseRedirect(reverse("reports_home", args=(domain,)) + '#scheduled-reports')

def _can_send_test_report(report_id, user, domain):
    try:
        report = ReportNotification.get(report_id)
    except ResourceNotFound:
        return False

    if report.domain != domain:
        return False

    return user._id == report.owner._id or user.is_domain_admin(domain)


def get_scheduled_report_response(couch_user, domain, scheduled_report_id,
                                  email=True, attach_excel=False,
                                  send_only_active=False, request=None):
    """
    This function somewhat confusingly returns a tuple of: (response, excel_files)
    If attach_excel is false, excel_files will always be an empty list.
    If send_only_active is True, then only ReportConfigs that have a start_date
    in the past will be sent. If none of the ReportConfigs are valid, no email will
    be sent.
    """
    # todo: clean up this API?
    domain_obj = Domain.get_by_name(domain)
    if not user_can_view_reports(domain_obj, couch_user):
        raise Http404

    scheduled_report = ReportNotification.get_report(scheduled_report_id)
    if not scheduled_report:
        raise Http404

    if not (scheduled_report.domain == domain and scheduled_report.can_be_viewed_by(couch_user)):
        raise Http404

    from django.http import HttpRequest
    if not request:
        request = HttpRequest()
        request.couch_user = couch_user
        request.user = couch_user.get_django_user()
        request.domain = domain
        request.couch_user.current_domain = domain

    return _render_report_configs(
        request,
        scheduled_report.configs,
        scheduled_report.domain,
        scheduled_report.owner_id,
        couch_user,
        email,
        attach_excel=attach_excel,
        lang=scheduled_report.language,
        send_only_active=send_only_active,
    )


def _render_report_configs(request, configs, domain, owner_id, couch_user, email,
                           notes=None, attach_excel=False, once=False, lang=None,
                           send_only_active=False):
    """
    Renders only notification's main content, which then may be used to generate full notification body.

    :returns: two-tuple `(report_text: str, excel_files: list)`. Both
    values are empty when there are no applicable report configs.
    `excel_files` is a list of dicts.
    """
    from dimagi.utils.web import get_url_base

    report_outputs = []
    excel_attachments = []
    format = Format.from_format(request.GET.get('format') or Format.XLS_2007)

    # Show only the report configs that have started their reporting period
    if send_only_active:
        configs = [c for c in configs if c.is_active]

    # Don't send an email if none of the reports configs have started
    if len(configs) == 0:
        return "", []

    for config in configs:
        content, excel_file = config.get_report_content(lang, attach_excel=attach_excel, couch_user=couch_user)
        if excel_file:
            excel_attachments.append({
                'title': config.full_name + "." + format.extension,
                'file_obj': excel_file,
                'mimetype': format.mimetype
            })
        date_range = config.get_date_range()
        report_outputs.append({
            'title': config.full_name,
            'url': config.url,
            'content': content,
            'is_active': config.is_active,
            'description': config.description,
            "startdate": date_range.get("startdate") if date_range else "",
            "enddate": date_range.get("enddate") if date_range else "",
        })

    response = render(request, "reports/report_email_content.html", {
        "reports": report_outputs,
        "domain": domain,
        "couch_user": owner_id,
        "DNS_name": get_url_base(),
        "owner_name": couch_user.full_name or couch_user.get_email(),
        "email": email,
        "notes": notes,
        "report_type": _("once off report") if once else _("scheduled report"),
    })
    return response.content.decode("utf-8"), excel_attachments


def render_full_report_notification(request, content, email=None, report_notification=None):
    """
    Renders full notification body with provided main content.
    """
    from dimagi.utils.web import get_url_base
    from django.http import HttpRequest

    if request is None:
        request = HttpRequest()

    unsub_link = None
    if report_notification and email:
        unsub_link = get_url_base() + reverse('notification_unsubscribe', kwargs={
            'scheduled_report_id': report_notification._id,
            'user_email': email,
            'scheduled_report_secret': report_notification.get_secret(email)
        })

    return render(request, "reports/report_email.html", {
        'email_content': content,
        'unsub_link': unsub_link
    })


@login_and_domain_required
def view_scheduled_report(request, domain, scheduled_report_id):
    report_text = get_scheduled_report_response(request.couch_user, domain, scheduled_report_id, email=False)[0]
    return render_full_report_notification(request, report_text)


def safely_get_case(request, domain, case_id):
    """Get case if accessible else raise a 404 or 403"""
    case = get_case_or_404(domain, case_id)
    if not (request.can_access_all_locations or
            user_can_access_case(domain, request.couch_user, case)):
        raise location_restricted_exception(request)
    return case


@location_safe
class CaseDataView(BaseProjectReportSectionView):
    urlname = 'case_data'
    template_name = "reports/reportdata/case_data.html"
    page_title = ugettext_lazy("Case Data")
    http_method_names = ['get']

    @method_decorator(require_case_view_permission)
    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if not self.case_instance:
            messages.info(request,
                          _("Sorry, we couldn't find that case. If you think this "
                            "is a mistake please report an issue."))
            return HttpResponseRedirect(CaseListReport.get_url(domain=self.domain))
        if not (request.can_access_all_locations or
                user_can_access_case(self.domain, self.request.couch_user, self.case_instance)):
            raise location_restricted_exception(request)
        return super(CaseDataView, self).dispatch(request, *args, **kwargs)

    @property
    def case_id(self):
        return self.kwargs['case_id']

    @property
    @memoized
    def case_instance(self):
        try:
            case = CaseAccessors(self.domain).get_case(self.case_id)
            if case.domain != self.domain or case.is_deleted:
                return None
            return case
        except CaseNotFound:
            return None

    @property
    def page_name(self):
        return case_inline_display(self.case_instance)

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.case_id,))

    @property
    def parent_pages(self):
        return [{
            'title': CaseListReport.name,
            'url': CaseListReport.get_url(domain=self.domain),
        }]

    @property
    def page_context(self):
        opening_transactions = self.case_instance.get_opening_transactions()
        if not opening_transactions:
            messages.error(self.request, _(
                "The case creation form could not be found. "
                "Usually this happens if the form that created the case is archived "
                "but there are other forms that updated the case. "
                "To fix this you can archive the other forms listed here."
            ))

        from corehq.apps.hqwebapp.templatetags.proptable_tags import get_tables_as_rows, get_default_definition
        wrapped_case = get_wrapped_case(self.case_instance)
        timezone = get_timezone_for_user(self.request.couch_user, self.domain)
        # Get correct timezone for the current date: https://github.com/dimagi/commcare-hq/pull/5324
        timezone = timezone.localize(datetime.utcnow()).tzinfo
        _get_tables_as_rows = partial(get_tables_as_rows, timezone=timezone)
        show_transaction_export = toggles.COMMTRACK.enabled(self.request.user.username)

        def _get_case_url(case_id):
            return absolute_reverse(self.urlname, args=[self.domain, case_id])

        data = copy.deepcopy(wrapped_case.to_full_dict())
        display = wrapped_case.get_display_config()
        default_properties = _get_tables_as_rows(data, display)
        dynamic_data = wrapped_case.dynamic_properties()

        for section in display:
            for row in section['layout']:
                for item in row:
                    dynamic_data.pop(item.expr, None)

        if dynamic_data:
            dynamic_keys = sorted(dynamic_data.keys())
            definition = get_default_definition(
                dynamic_keys, num_columns=DYNAMIC_CASE_PROPERTIES_COLUMNS)

            dynamic_properties = _get_tables_as_rows(
                dynamic_data,
                definition,
            )
        else:
            dynamic_properties = None

        the_time_is_now = datetime.utcnow()
        tz_offset_ms = int(timezone.utcoffset(the_time_is_now).total_seconds()) * 1000
        tz_abbrev = timezone.localize(the_time_is_now).tzname()

        product_name_by_id = {
            product['product_id']: product['name']
            for product in SQLProduct.objects.filter(domain=self.domain).values('product_id', 'name').all()
        }

        def _product_name(product_id):
            return product_name_by_id.get(product_id, _('Unknown Product ("{}")').format(product_id))

        ledger_map = LedgerAccessors(self.domain).get_case_ledger_state(self.case_id, ensure_form_id=True)
        for section, entry_map in ledger_map.items():
            product_tuples = [
                (_product_name(product_id), entry_map[product_id])
                for product_id in entry_map
            ]
            product_tuples.sort(key=lambda x: x[0])
            ledger_map[section] = product_tuples

        repeat_records = get_repeat_records_by_payload_id(self.domain, self.case_id)

        can_edit_data = self.request.couch_user.can_edit_data
        show_properties_edit = (
            can_edit_data
            and has_privilege(self.request, privileges.DATA_CLEANUP)
        )

        context = {
            "case_id": self.case_id,
            "case": self.case_instance,
            "show_case_rebuild": toggles.SUPPORT.enabled(self.request.user.username),
            "can_edit_data": can_edit_data,
            "is_usercase": self.case_instance.type == USERCASE_TYPE,

            "default_properties_as_table": default_properties,
            "dynamic_properties": dynamic_data,
            "dynamic_properties_as_table": dynamic_properties,
            "show_properties_edit": show_properties_edit,
            "timezone": timezone,
            "tz_abbrev": tz_abbrev,
            "ledgers": ledger_map,
            "timezone_offset": tz_offset_ms,
            "show_transaction_export": show_transaction_export,
            "xform_api_url": reverse('single_case_forms', args=[self.domain, self.case_id]),
            "repeat_records": repeat_records,
        }
        context.update(case_hierarchy_context(self.case_instance, _get_case_url, timezone=timezone))
        return context


def form_to_json(domain, form, timezone):
    form_name = xmlns_to_name(
        domain,
        form.xmlns,
        app_id=form.app_id,
        lang=get_language(),
    )
    received_on = ServerTime(form.received_on).user_time(timezone).done().strftime("%Y-%m-%d %H:%M")

    return {
        'id': form.form_id,
        'received_on': received_on,
        'user': {
            "id": form.user_id or '',
            "username": form.metadata.username if form.metadata else '',
        },
        'readable_name': form_name,
    }


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_forms(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    try:
        start_range = int(request.GET['start_range'])
        end_range = int(request.GET['end_range'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    slice = list(reversed(case.xform_ids))[start_range:end_range]
    forms = FormAccessors(domain).get_forms(slice, ordered=True)
    timezone = get_timezone_for_user(request.couch_user, domain)
    return json_response([
        form_to_json(domain, form, timezone) for form in forms
    ])


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def case_property_changes(request, domain, case_id, case_property_name):
    """Returns all changes to a case property
    """
    case = safely_get_case(request, domain, case_id)
    timezone = get_timezone_for_user(request.couch_user, domain)
    next_transaction = int(request.GET.get('next_transaction', 0))

    paged_changes, last_transaction_checked = get_paged_changes_to_case_property(
        case,
        case_property_name,
        start=next_transaction,
    )

    changes = []
    for change in paged_changes:
        change_json = form_to_json(domain, change.transaction.form, timezone)
        change_json['new_value'] = change.new_value
        change_json['form_url'] = reverse('render_form_data', args=[domain, change.transaction.form.form_id])
        changes.append(change_json)

    return json_response({
        'changes': changes,
        'last_transaction_checked': last_transaction_checked,
    })


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def download_case_history(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    track_workflow(request.couch_user.username, "Case Data Page: Case History csv Downloaded")
    history = get_case_history(case)
    properties = set()
    for f in history:
        properties |= set(f.keys())
    properties = sorted(list(properties))
    columns = [properties]
    for f in history:
        columns.append([f.get(prop, '') for prop in properties])

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="case_history_{}.csv"'.format(case.name)

    writer = csv.writer(response)
    writer.writerows(zip(*columns))   # transpose the columns to rows
    return response


@location_safe
class CaseAttachmentsView(CaseDataView):
    urlname = 'single_case_attachments'
    template_name = "reports/reportdata/case_attachments.html"
    page_title = ugettext_lazy("Case Attachments")
    http_method_names = ['get']

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not can_view_attachments(request):
            return HttpResponseForbidden(_("You don't have permission to access this page."))
        return super(CaseAttachmentsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_name(self):
        return "{} '{}'".format(
            _("Attachments for case"), super(CaseAttachmentsView, self).page_name
        )


@require_case_view_permission
@login_and_domain_required
@require_GET
def case_xml(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    version = request.GET.get('version', V2)
    return HttpResponse(case.to_xml(version), content_type='text/xml')


@location_safe
@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_GET
def case_property_names(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)

    # We need to look at the export schema in order to remove any case properties that
    # have been deleted from the app. When the data dictionary is fully public, we can use that
    # so that users may deprecate those properties manually
    export_schema = CaseExportDataSchema.generate_schema_from_builds(domain, None, case.type)
    property_schema = export_schema.group_schemas[0]
    last_app_ids = get_latest_app_ids_and_versions(domain)
    all_property_names = {
        item.path[-1].name for item in property_schema.items
        if not is_occurrence_deleted(item.last_occurrences, last_app_ids) and '/' not in item.path[-1].name
    }
    all_property_names = all_property_names.difference(KNOWN_CASE_PROPERTIES)
    # external_id is effectively a dynamic property: see CaseDisplayWrapper.dynamic_properties
    if case.external_id:
        all_property_names.add('external_id')

    return json_response(sorted(all_property_names, key=lambda item: item.lower()))


@location_safe
@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def edit_case_view(request, domain, case_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    case = safely_get_case(request, domain, case_id)
    user = request.couch_user

    old_properties = case.dynamic_case_properties()
    old_properties['external_id'] = None    # special handling below
    updates = _get_data_cleaning_updates(request, old_properties)

    case_block_kwargs = {}

    # User may also update external_id; see CaseDisplayWrapper.dynamic_properties
    if 'external_id' in updates:
        if updates['external_id'] != case.external_id:
            case_block_kwargs['external_id'] = updates['external_id']
        updates.pop('external_id')

    if updates:
        case_block_kwargs['update'] = updates

    if case_block_kwargs:
        submit_case_blocks([CaseBlock.deprecated_init(case_id=case_id, **case_block_kwargs).as_text()],
            domain, username=user.username, user_id=user._id, device_id=__name__ + ".edit_case",
            xmlns=EDIT_FORM_XMLNS)
        messages.success(request, _('Case properties saved for %s.' % case.name))
    else:
        messages.success(request, _('No changes made to %s.' % case.name))
    return JsonResponse({'success': 1})


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def rebuild_case_view(request, domain, case_id):
    case = get_case_or_404(domain, case_id)
    rebuild_case_from_forms(domain, case_id, UserRequestedRebuild(user_id=request.couch_user.user_id))
    messages.success(request, _('Case %s was rebuilt from its forms.' % case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def resave_case_view(request, domain, case_id):
    """Re-save the case to have it re-processed by pillows
    """
    case = get_case_or_404(domain, case_id)
    resave_case(domain, case)
    messages.success(
        request,
        _('Case %s was successfully saved. Hopefully it will show up in all reports momentarily.' % case.name),
    )
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@location_safe
@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def close_case_view(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    if case.closed:
        messages.info(request, 'Case {} is already closed.'.format(case.name))
    else:
        device_id = __name__ + ".close_case_view"
        form_id = close_case(case_id, domain, request.couch_user, device_id)
        msg = format_html(
            _('''Case {name} has been closed.
            <a href="{url}" class="post-link">Undo</a>.
            You can also reopen the case in the future by archiving the last form in the case history.
        '''),
            name=case.name,
            url=reverse('undo_close_case', args=[domain, case_id, form_id]),
        )
        messages.success(request, msg, extra_tags='html')
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@location_safe
@require_case_view_permission
@require_permission(Permissions.edit_data)
@require_POST
def undo_close_case_view(request, domain, case_id, xform_id):
    case = safely_get_case(request, domain, case_id)
    if not case.closed:
        messages.info(request, 'Case {} is not closed.'.format(case.name))
    else:
        closing_form_id = xform_id
        assert closing_form_id in case.xform_ids
        form = FormAccessors(domain).get_form(closing_form_id)
        form.archive(user_id=request.couch_user._id)
        messages.success(request, 'Case {} has been reopened.'.format(case.name))
    return HttpResponseRedirect(reverse('case_data', args=[domain, case_id]))


@location_safe
@require_case_view_permission
@login_and_domain_required
@require_GET
def export_case_transactions(request, domain, case_id):
    case = safely_get_case(request, domain, case_id)
    products_by_id = dict(SQLProduct.objects.filter(domain=domain).values_list('product_id', 'name'))

    headers = [
        _('case id'),
        _('case name'),
        _('section'),
        _('date'),
        _('product_id'),
        _('product_name'),
        _('transaction amount'),
        _('type'),
        _('ending balance'),
    ]

    def _make_row(transaction):
        return [
            transaction.case_id,
            case.name,
            transaction.section_id,
            transaction.report_date or '',
            transaction.entry_id,
            products_by_id.get(transaction.entry_id, _('unknown product')),
            transaction.delta,
            transaction.type,
            transaction.stock_on_hand,
        ]

    transactions = sorted(
        LedgerAccessors.get_ledger_transactions_for_case(case_id),
        key=lambda tx: (tx.section_id, tx.report_date)
    )

    formatted_table = [
        [
            'ledger transactions',
            [headers] + [_make_row(txn) for txn in transactions]
        ]
    ]
    tmp = io.StringIO()
    export_from_tables(formatted_table, tmp, 'xlsx')
    return export_response(tmp, 'xlsx', '{}-stock-transactions'.format(case.name))


def _get_form_context(request, domain, instance):
    timezone = get_timezone_for_user(request.couch_user, domain)
    try:
        assert domain == instance.domain
    except AssertionError:
        raise Http404()

    context = {
        "domain": domain,
        "timezone": timezone,
        "instance": instance,
        "user": request.couch_user,
        "request": request,
    }
    return context


def _get_form_render_context(request, domain, instance, case_id=None):
    context = _get_form_context(request, domain, instance)
    user = context['user']
    timezone = context['timezone']
    support_enabled = toggle_enabled(request, toggles.SUPPORT)

    form_data, question_list_not_found = get_readable_data_for_submission(instance)

    # Build ordered list of questions and dict of question values => responses
    # Question values will be formatted to be processed by XFormQuestionValueIterator,
    # for example "/data/group/repeat_group[2]/question_id"
    try:
        question_response_map, ordered_question_values = get_data_cleaning_data(form_data, instance)
    except AttributeError as err:
        question_response_map, ordered_question_values = (None, None)
        import logging
        logging.exception(err)

    context.update({
        "context_case_id": case_id,
        "instance": instance,
        "is_archived": instance.is_archived,
        "form_source_download_url": get_form_source_download_url(instance),
        "edit_info": _get_edit_info(instance),
        "domain": domain,
        "question_list_not_found": question_list_not_found,
        "form_data": form_data,
        "question_response_map": question_response_map,
        "ordered_question_values": ordered_question_values,
        "tz_abbrev": timezone.localize(datetime.utcnow()).tzname(),
    })

    context.update(_get_cases_changed_context(domain, instance, case_id))
    context.update(_get_form_metadata_context(domain, instance, timezone, support_enabled))
    context.update(_get_display_options(request, domain, user, instance, support_enabled))
    context.update(_get_edit_info(instance))

    instance_history = []
    if instance.history:
        form_operations = {
            'archive': ugettext_lazy('Archive'),
            'unarchive': ugettext_lazy('Un-Archive'),
            'edit': ugettext_lazy('Edit'),
            'uuid_data_fix': ugettext_lazy('Duplicate ID fix')
        }
        for operation in instance.history:
            user_date = ServerTime(operation.date).user_time(timezone).done()
            instance_history.append({
                'readable_date': user_date.strftime("%Y-%m-%d %H:%M"),
                'readable_action': form_operations.get(operation.operation, operation.operation),
                'user_info': get_doc_info_by_id(domain, operation.user),
            })
    context['instance_history'] = instance_history

    return context


def _get_cases_changed_context(domain, form, case_id=None):
    case_blocks = extract_case_blocks(form)
    for i, block in enumerate(list(case_blocks)):
        if case_id and block.get(const.CASE_ATTR_ID) == case_id:
            case_blocks.pop(i)
            case_blocks.insert(0, block)
    cases = []
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_default_definition, get_tables_as_columns

    def _sorted_case_update_keys(keys):
        """Put common @ attributes at the bottom"""
        return sorted(keys, key=lambda k: (k[0] == '@', k))

    for b in case_blocks:
        this_case_id = b.get(const.CASE_ATTR_ID)
        try:
            this_case = CaseAccessors(domain).get_case(this_case_id) if this_case_id else None
            valid_case = True
        except ResourceNotFound:
            this_case = None
            valid_case = False

        if this_case and this_case.case_id:
            url = reverse('case_data', args=[domain, this_case.case_id])
        else:
            url = "#"

        keys = _sorted_case_update_keys(list(b))
        assume_phonetimes = not form.metadata or form.metadata.deviceID != CLOUDCARE_DEVICE_ID
        definition = get_default_definition(
            keys,
            phonetime_fields=keys if assume_phonetimes else {},
        )
        cases.append({
            "is_current_case": case_id and this_case_id == case_id,
            "name": case_inline_display(this_case),
            "table": get_tables_as_columns(b, definition, timezone=get_timezone_for_request()),
            "url": url,
            "valid_case": valid_case,
            "case_type": this_case.type if this_case and valid_case else None,
        })

    return {
        'cases': cases
    }


def _get_form_metadata_context(domain, form, timezone, support_enabled=False):
    from corehq.apps.hqwebapp.templatetags.proptable_tags import get_default_definition, get_tables_as_columns

    meta = _top_level_tags(form).get('meta', None) or {}

    meta['received_on'] = json_format_datetime(form.received_on)
    meta['server_modified_on'] = json_format_datetime(form.server_modified_on) if form.server_modified_on else ''
    if support_enabled:
        meta['last_sync_token'] = form.last_sync_token

    phonetime_fields = ['timeStart', 'timeEnd']
    date_fields = ['received_on', 'server_modified_on'] + phonetime_fields
    definition = get_default_definition(
        _sorted_form_metadata_keys(list(meta)), phonetime_fields=phonetime_fields, date_fields=date_fields
    )
    form_meta_data = get_tables_as_columns(meta, definition, timezone=timezone)
    if getattr(form, 'auth_context', None):
        auth_context = AuthContext(form.auth_context)
        auth_context_user_id = auth_context.user_id
        auth_user_info = get_doc_info_by_id(None, auth_context_user_id)
    else:
        auth_user_info = get_doc_info_by_id(domain, None)
        auth_context = AuthContext(
            user_id=None,
            authenticated=False,
            domain=domain,
        )
    meta_userID = meta.get('userID')
    meta_username = meta.get('username')
    if meta_userID == 'demo_user':
        user_info = DocInfo(
            domain=domain,
            display='demo_user',
        )
    elif meta_username in ('admin', 'system'):
        user_info = DocInfo(
            domain=domain,
            display=meta_username,
        )
    else:
        user_info = get_doc_info_by_id(None, meta_userID)

    return {
        "form_meta_data": form_meta_data,
        "auth_context": auth_context,
        "auth_user_info": auth_user_info,
        "user_info": user_info,
    }


def _top_level_tags(form):
        """
        Returns a OrderedDict of the top level tags found in the xml, in the
        order they are found.

        The actual values are taken from the form JSON data and not from the XML
        """
        to_return = OrderedDict()

        element = form.get_xml_element()
        if element is None:
            return OrderedDict(sorted(form.form_data.items()))

        for child in element:
            # fix {namespace}tag format forced by ElementTree in certain cases (eg, <reg> instead of <n0:reg>)
            key = child.tag.split('}')[1] if child.tag.startswith("{") else child.tag
            if key == "Meta":
                key = "meta"
            to_return[key] = form.get_data('form/' + key)
        return to_return


def _sorted_form_metadata_keys(keys):
    def mycmp(x, y):
        foo = ('timeStart', 'timeEnd')
        bar = ('username', 'userID')

        if x in foo and y in foo:
            return -1 if foo.index(x) == 0 else 1
        elif x in foo or y in foo:
            return 0

        if x in bar and y in bar:
            return -1 if bar.index(x) == 0 else 1
        elif x in bar and y in bar:
            return 0

        return cmp(x, y)
    return sorted(keys, key=cmp_to_key(mycmp))


def _get_edit_info(instance):
    info = {
        'was_edited': False,
        'is_edit': False,
    }
    if instance.is_deprecated:
        info.update({
            'was_edited': True,
            'latest_version': instance.orig_id,
        })
    if getattr(instance, 'edited_on', None) and getattr(instance, 'deprecated_form_id', None):
        info.update({
            'is_edit': True,
            'edited_on': instance.edited_on,
            'previous_version': instance.deprecated_form_id
        })
    return info


def _get_display_options(request, domain, user, form, support_enabled):
    user_can_edit = (
        request and user and request.domain and user.can_edit_data()
    )
    show_edit_options = (
        user_can_edit
        and can_edit_form_location(domain, user, form)
    )
    show_edit_submission = (
        user_can_edit
        and has_privilege(request, privileges.DATA_CLEANUP)
        and not form.is_deprecated
    )

    show_resave = (
        user_can_edit and support_enabled
    )

    return {
        "show_edit_options": show_edit_options,
        "show_edit_submission": show_edit_submission,
        "show_resave": show_resave,
    }


def safely_get_form(request, domain, instance_id):
    """Fetches a form and verifies that the user can access it."""
    form = get_form_or_404(domain, instance_id)
    if not can_edit_form_location(domain, request.couch_user, form):
        raise location_restricted_exception(request)
    return form


@location_safe
class FormDataView(BaseProjectReportSectionView):
    urlname = 'render_form_data'
    page_title = ugettext_lazy("Untitled Form")
    template_name = "reports/reportdata/form_data.html"
    http_method_names = ['get']

    @method_decorator(require_form_view_permission)
    def dispatch(self, request, *args, **kwargs):
        return super(FormDataView, self).dispatch(request, *args, **kwargs)

    @property
    def instance_id(self):
        return self.kwargs['instance_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.instance_id,))

    @property
    @memoized
    def xform_instance(self):
        return safely_get_form(self.request, self.domain, self.instance_id)

    @property
    @memoized
    def form_name(self):
        try:
            form_name = self.xform_instance.form_data["@name"]
        except KeyError:
            form_name = _("Untitled Form")
        return form_name

    @property
    def page_name(self):
        return self.form_name

    @property
    def parent_pages(self):
        return [{
            'title': inspect.SubmitHistory.name,
            'url': inspect.SubmitHistory.get_url(self.domain),
        }]

    @property
    def page_context(self):
        page_context = _get_form_render_context(self.request, self.domain, self.xform_instance)
        page_context.update({
            "slug": inspect.SubmitHistory.slug,
            "form_name": self.form_name,
            "form_received_on": self.xform_instance.received_on,
        })
        return page_context


@location_safe
@require_form_view_permission
@login_and_domain_required
@require_GET
def case_form_data(request, domain, case_id, xform_id):
    instance = get_form_or_404(domain, xform_id)
    if not can_edit_form_location(domain, request.couch_user, instance):
        # This can happen if a user can view the case but not a particular form
        return JsonResponse({
            'html': _("You do not have permission to view this form."),
        }, status=403)
    context = _get_form_render_context(request, domain, instance, case_id)
    return JsonResponse({
        'html': render_to_string("reports/form/partials/single_form.html", context, request=request),
        'xform_id': xform_id,
        'question_response_map': context['question_response_map'],
        'ordered_question_values': context['ordered_question_values'],
    })


@require_form_view_permission
@login_and_domain_required
@require_GET
def download_form(request, domain, instance_id):
    instance = get_form_or_404(domain, instance_id)
    assert(domain == instance.domain)

    response = HttpResponse(content_type='application/xml')
    response.write(instance.get_xml())
    return response


@location_safe
class EditFormInstance(View):

    @method_decorator(require_form_view_permission)
    @method_decorator(require_permission(Permissions.edit_data))
    def dispatch(self, request, *args, **kwargs):
        return super(EditFormInstance, self).dispatch(request, args, kwargs)

    @staticmethod
    def _get_form_from_instance(instance):
        try:
            build = Application.get(instance.build_id)
        except ResourceNotFound:
            raise Http404(_('Application not found.'))

        forms = build.get_forms_by_xmlns(instance.xmlns)
        if not forms:
            raise Http404(_('Missing module or form information!'))
        non_shadow_forms = [form for form in forms if form.form_type != ShadowForm.form_type]
        return non_shadow_forms[0]

    @staticmethod
    def _form_instance_to_context_url(domain, instance):
        form = EditFormInstance._get_form_from_instance(instance)
        return reverse(
            'cloudcare_form_context',
            args=[domain, instance.build_id, form.get_module().id, form.id],
            params={'instance_id': instance.form_id}
        )

    def get(self, request, *args, **kwargs):
        domain = request.domain
        instance_id = self.kwargs.get('instance_id', None)

        def _error(msg):
            messages.error(request, msg)
            url = reverse('render_form_data', args=[domain, instance_id])
            return HttpResponseRedirect(url)

        if not (has_privilege(request, privileges.DATA_CLEANUP)) or not instance_id:
            raise Http404()

        instance = safely_get_form(request, domain, instance_id)
        context = _get_form_context(request, domain, instance)
        if not instance.app_id or not instance.build_id:
            deviceID = instance.metadata.deviceID
            if deviceID and deviceID == FORMPLAYER_DEVICE_ID:
                return _error(_(
                    "Could not detect the application or form for this submission. "
                    "A common cause is that the form was submitted via App or Form preview"
                ))
            else:
                return _error(_('Could not detect the application or form for this submission.'))

        user = CouchUser.get_by_user_id(instance.metadata.userID, domain)
        if not user:
            return _error(_('Could not find user for this submission.'))

        edit_session_data = get_user_contributions_to_touchforms_session(domain, user)

        # add usercase to session
        form = self._get_form_from_instance(instance)

        try:
            validate_xform_for_edit(form.wrapped_xform())
        except EditFormValidationError as e:
            return _error(e)

        if form.uses_usercase():
            usercase_id = user.get_usercase_id()
            if not usercase_id:
                return _error(_('Could not find the user-case for this form'))
            edit_session_data[USERCASE_ID] = usercase_id

        case_blocks = extract_case_blocks(instance, include_path=True)
        if form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            datums = EntriesHelper(form.get_app()).get_datums_meta_for_form_generic(form)
            for case_block in case_blocks:
                path = case_block.path[0]  # all case blocks in advanced forms are nested one level deep
                matching_datums = [datum for datum in datums if datum.action.form_element_name == path]
                if len(matching_datums) == 1:
                    edit_session_data[matching_datums[0].datum.id] = case_block.caseblock.get(const.CASE_ATTR_ID)
        else:
            # a bit hacky - the app manager puts the main case directly in the form, so it won't have
            # any other path associated with it. This allows us to differentiate from parent cases.
            # You might think that you need to populate other session variables like parent_id, but those
            # are never actually used in the form.
            non_parents = [cb for cb in case_blocks if cb.path == []]
            if len(non_parents) == 1:
                edit_session_data['case_id'] = non_parents[0].caseblock.get(const.CASE_ATTR_ID)
                case = CaseAccessors(domain).get_case(edit_session_data['case_id'])
                if case.closed:
                    message = format_html(_(
                        'Case <a href="{case_url}">{case_name}</a> is closed. Please reopen the '
                        'case before editing the form'),
                        case_url=reverse('case_data', args=[domain, case.case_id]),
                        case_name=case.name,
                    )
                    return _error(message)
                elif case.is_deleted:
                    message = format_html(_(
                        'Case <a href="{case_url}">{case_name}</a> is deleted. Cannot edit this form.'),
                        case_url=reverse('case_data', args=[domain, case.case_id]),
                        case_name=case.name,
                    )
                    return _error(message)

        edit_session_data['is_editing'] = True
        edit_session_data['function_context'] = {
            'static-date': [
                {'name': 'now', 'value': instance.metadata.timeEnd},
                {'name': 'today', 'value': instance.metadata.timeEnd.date()},
            ]
        }

        context.update({
            'domain': domain,
            "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
            'form_name': _('Edit Submission'),  # used in breadcrumbs
            'use_sqlite_backend': use_sqlite_backend(domain),
            'username': context.get('user').username,
            'edit_context': {
                'formUrl': self._form_instance_to_context_url(domain, instance),
                'submitUrl': reverse('receiver_secure_post_with_app_id', args=[domain, instance.build_id]),
                'sessionData': edit_session_data,
                'returnUrl': reverse('render_form_data', args=[domain, instance_id]),
                'domain': domain,
            }
        })
        return render(request, 'reports/form/edit_submission.html', context)


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def restore_edit(request, domain, instance_id):
    if not (has_privilege(request, privileges.DATA_CLEANUP)):
        raise Http404()

    instance = safely_get_form(request, domain, instance_id)
    if instance.is_deprecated:
        submit_form_locally(instance.get_xml(), domain, app_id=instance.app_id, build_id=instance.build_id)
        messages.success(request, _('Form was restored from a previous version.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance.orig_id]))
    else:
        messages.warning(request, _('Sorry, that form cannot be edited.'))
        return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def archive_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    case_id_from_request, redirect = _get_case_id_and_redirect_url(domain, request)

    notify_level = messages.SUCCESS
    if instance.is_normal:
        cases_with_other_forms = _get_cases_with_other_forms(domain, instance)
        if cases_with_other_forms:
            notify_msg = _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request)
            notify_level = messages.ERROR
        else:
            instance.archive(user_id=request.couch_user._id)
            notify_msg = _("Form was successfully archived.")
    elif instance.is_archived:
        notify_msg = _("Form was already archived.")
    else:
        notify_msg = _("Can't archive documents of type %s. How did you get here??") % instance.doc_type
        notify_level = messages.ERROR

    params = {
        "notif": notify_msg,
        "undo": _("Undo"),
        "url": reverse('unarchive_form', args=[domain, instance_id]),
    }

    msg_template = "{notif} <a href='{url}' class='post-link'>{undo}</a>" if instance.is_archived else '{notif}'
    msg = format_html(msg_template, **params)
    messages.add_message(request, notify_level, msg, extra_tags='html')

    return HttpResponseRedirect(redirect)


def _get_cases_with_forms_message(domain, cases_with_other_forms, case_id_from_request):
    def _get_all_case_links():
        all_case_links = []
        for case_id, case_name in cases_with_other_forms.items():
            if case_id == case_id_from_request:
                all_case_links.append(format_html(
                    _("{} (this case)"),
                    case_name
                ))
            else:
                all_case_links.append(format_html(
                    '<a href="{}#!history">{}</a>',
                    reverse("case_data", args=[domain, case_id]),
                    case_name
                ))
        return all_case_links

    case_links = format_html_join(", ", "{}", ((link,) for link in _get_all_case_links()))

    msg = _("""Form cannot be archived as it creates cases that are updated by other forms.
        All other forms for these cases must be archived first:""")
    return format_html("{} {}", msg, case_links)


def _get_cases_with_other_forms(domain, xform):
    """Get all cases touched by this form which also have other forms associated with them.
    :returns: Dict of Case ID -> Case"""
    cases_created = {u.id for u in get_case_updates(xform) if u.creates_case()}
    cases = {}
    for case in CaseAccessors(domain).iter_cases(list(cases_created)):
        if not case.is_deleted and case.xform_ids != [xform.form_id]:
            # case has other forms that need to be archived before this one
            cases[case.case_id] = case.name
    return cases


def _get_case_id_and_redirect_url(domain, request):
    case_id = None
    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = inspect.SubmitHistory.get_url(domain)
    else:
        # check if referring URL was a case detail view, then make sure
        # the case still exists before redirecting.
        template = reverse('case_data', args=[domain, 'fake_case_id'])
        template = template.replace('fake_case_id', '([^/]*)')
        case_id = re.findall(template, redirect)
        if case_id:
            case_id = case_id[0]
            try:
                case = CaseAccessors(domain).get_case(case_id)
                if case.is_deleted:
                    raise CaseNotFound
            except CaseNotFound:
                redirect = reverse('project_report_dispatcher', args=[domain, 'case_list'])
    return case_id, redirect


@require_form_view_permission
@require_permission(Permissions.edit_data)
@location_safe
def unarchive_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    if instance.is_archived:
        instance.unarchive(user_id=request.couch_user._id)
    else:
        assert instance.is_normal
    messages.success(request, _("Form was successfully restored."))

    redirect = request.META.get('HTTP_REFERER')
    if not redirect:
        redirect = reverse('render_form_data', args=[domain, instance_id])
    return HttpResponseRedirect(redirect)


def _get_data_cleaning_updates(request, old_properties):
    updates = {}
    properties = json.loads(request.POST.get('properties'))

    def _get_value(val_or_dict):
        if isinstance(val_or_dict, dict):
            return val_or_dict.get('value')
        else:
            return val_or_dict

    for prop, value in properties.items():
        if prop not in old_properties or _get_value(old_properties[prop]) != value:
            updates[prop] = value
    return updates


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def edit_form(request, domain, instance_id):
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain

    form_data, question_list_not_found = get_readable_data_for_submission(instance)
    old_properties, dummy = get_data_cleaning_data(form_data, instance)
    updates = _get_data_cleaning_updates(request, old_properties)

    if updates:
        errors = FormProcessorInterface(domain).update_responses(instance, updates, request.couch_user.get_id)
        if errors:
            messages.error(request, _('Could not update questions: {}').format(", ".join(errors)))
        else:
            messages.success(request, _('Question responses saved.'))
    else:
        messages.info(request, _('No changes made to form.'))

    return JsonResponse({'success': 1})


@require_form_view_permission
@require_permission(Permissions.edit_data)
@require_POST
@location_safe
def resave_form_view(request, domain, instance_id):
    """Re-save the form to have it re-processed by pillows
    """
    from corehq.form_processor.change_publishers import publish_form_saved
    instance = safely_get_form(request, domain, instance_id)
    assert instance.domain == domain
    resave_form(domain, instance)
    messages.success(request, _("Form was successfully resaved. It should reappear in reports shortly."))
    return HttpResponseRedirect(reverse('render_form_data', args=[domain, instance_id]))


def _is_location_safe_report_class(view_fn, request, domain, export_hash, format):
    db = get_blob_db()

    try:
        meta = db.metadb.get(parent_id=export_hash, key=export_hash)
    except models.BlobMeta.DoesNotExist:
        # The report doesn't exist, so let the export code handle the response
        return True

    return report_class_is_location_safe(meta.properties["report_class"])


# TODO: This should be renamed to better convey what the function does.
# Export suggests that this is exporting data, but this is actually the function
# that retrieves the data that was previously exported.
@conditionally_location_safe(_is_location_safe_report_class)
@login_and_domain_required
@require_GET
def export_report(request, domain, export_hash, format):
    db = get_blob_db()
    report_not_found = HttpResponseNotFound(_("That report was not found. Please remember "
                                              "that download links expire after 24 hours."))

    try:
        meta = db.metadb.get(parent_id=export_hash, key=export_hash)
    except models.BlobMeta.DoesNotExist:
        return report_not_found

    if domain != meta.domain:
        raise Http404()

    report_class = meta.properties["report_class"]

    try:
        report_file = db.get(export_hash, type_code=CODES.tempfile)
    except NotFound:
        return report_not_found
    with report_file:
        if not request.couch_user.has_permission(domain, 'view_report', data=report_class):
            raise PermissionDenied()
        if format in Format.VALID_FORMATS:
            file = ContentFile(report_file.read())
            response = HttpResponse(file, Format.FORMAT_DICT[format])
            response['Content-Length'] = file.size
            response['Content-Disposition'] = 'attachment; filename="{filename}.{extension}"'.format(
                filename=meta.name or export_hash,
                extension=Format.FORMAT_DICT[format]['extension']
            )
            return response
        else:
            return HttpResponseNotFound(_("We don't support this format"))


@require_permission(Permissions.view_report, 'corehq.apps.reports.standard.project_health.ProjectHealthDashboard')
def project_health_user_details(request, domain, user_id):
    # todo: move to project_health.py? goes with project health dashboard.
    user = get_document_or_404(CommCareUser, domain, user_id)
    submission_by_form_link = '{}?emw=u__{}'.format(
        reverse('project_report_dispatcher', args=(domain, 'submissions_by_form')),
        user_id,
    )
    return render(request, 'reports/project_health/user_details.html', {
        'domain': domain,
        'user': user,
        'groups': ', '.join(g.name for g in Group.by_user_id(user_id)),
        'submission_by_form_link': submission_by_form_link,
    })


class TableauServerView(BaseProjectReportSectionView):
    urlname = 'tableau_server_view'
    page_title = ugettext_lazy('Tableau Server Config')
    template_name = 'hqwebapp/crispy/single_crispy_form.html'

    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauServerView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def tableau_server_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return TableauServerForm(
            data, domain=self.domain
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        kwargs['initial'] = TableauServer.objects.get_or_create(domain=self.domain)
        return kwargs

    @property
    def page_context(self):
        return {
            'form': self.tableau_server_form
        }

    def post(self, request, *args, **kwargs):
        if self.tableau_server_form.is_valid():
            self.tableau_server_form.save()
            messages.success(
                request, ugettext_lazy("Tableau Server Settings Updated")
            )
        else:
            messages.error(
                request, ugettext_lazy("Could not update Tableau Server Settings")
            )
        return self.get(request, *args, **kwargs)


class TableauVisualizationListView(BaseProjectReportSectionView, CRUDPaginatedViewMixin):
    urlname = 'tableau_visualization_list_view'
    page_title = _('Tableau Visualizations')
    template_name = 'reports/tableau_visualization.html'

    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauVisualizationListView, self).dispatch(request, *args, **kwargs)

    @property
    def total(self):
        return self.base_query.count()

    @property
    def base_query(self):
        return TableauVisualization.objects.filter(domain=self.domain)

    @property
    def column_names(self):
        return [
            _("Server"),
            _("View URL"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        start, end = self.skip, self.skip + self.limit
        for tableau_visualization in self.base_query.all()[start:end]:
            yield {
                "itemData": self._get_item_data(tableau_visualization),
                "template": "tableau-visualization-template",
            }

    def _get_item_data(self, tableau_visualization):
        data = {
            'id': tableau_visualization.id,
            'server': tableau_visualization.server.server_name,
            'view_url': tableau_visualization.view_url,
        }
        return data

    def get_deleted_item_data(self, item_id):
        tableau_viz = TableauVisualization.objects.get(
            pk=item_id,
            domain=self.domain,
        )
        tableau_viz.delete()
        return {
            'itemData': self._get_item_data(tableau_viz),
            'template': 'tableau-visualization-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


class TableauVisualizationDetailView(BaseProjectReportSectionView, ModelFormMixin, ProcessFormView):
    urlname = 'tableau_visualization_detail_view'
    page_title = _('Tableau Visualization')
    template_name = 'hqwebapp/crispy/single_crispy_form.html'
    model = TableauVisualization
    form_class = TableauVisualizationForm

    @method_decorator(toggles.EMBEDDED_TABLEAU.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(TableauVisualizationDetailView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(domain=self.domain)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.pk_url_kwarg in self.kwargs else None
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        return kwargs

    def get_success_url(self):
        return reverse(
            TableauVisualizationListView.urlname,
            kwargs={'domain': self.domain},
        )

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
