from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools
import six.moves.html_parser
import json
import socket
import uuid
from io import StringIO
from collections import defaultdict, namedtuple, OrderedDict, Counter
from datetime import timedelta, date, datetime

import dateutil
from couchdbkit import ResourceNotFound
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core import management, cache
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import mail_admins
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.http.response import Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _, ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView, View
from lxml import etree
from lxml.builder import E
from restkit import Resource
from restkit.errors import Unauthorized

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.callcenter.utils import CallCenterCase
from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.data_analytics.const import GIR_FIELDS
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.domain.models import Domain
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.apps.hqadmin.reporting.exceptions import HistoTypeNotFoundException
from corehq.apps.hqadmin.service_checks import run_checks
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from corehq.apps.users.util import format_username
from corehq.elastic import parse_args_for_es, run_query, ES_META
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.toggles import any_toggle_enabled, SUPPORT
from corehq.util import reverse
from corehq.util.couchdb_management import couch_config
from corehq.util.supervisord.api import (
    PillowtopSupervisorApi,
    SupervisorException,
    all_pillows_supervisor_status,
    pillow_supervisor_status
)
from corehq.util.timer import TimingContext
from couchforms.models import XFormInstance
from couchforms.openrosa_response import RESPONSE_XMLNS
from dimagi.utils.couch.database import get_db, is_bigcouch
from dimagi.utils.csv import UnicodeWriter
from dimagi.utils.dates import add_months
from dimagi.utils.decorators.datespan import datespan_in_request
from memoized import memoized
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from corehq.apps.hqadmin.tasks import send_mass_emails
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_all_pillows_json, get_pillow_json, get_pillow_config_by_name
from corehq.apps.hqadmin import service_checks, escheck
from corehq.apps.hqadmin.forms import (
    AuthenticateAsForm, BrokenBuildsForm, EmailForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)
from corehq.apps.hqadmin.history import get_recent_changes, download_changes
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.reporting.reports import get_project_spaces, get_stats_data, HISTO_TYPE_TO_FUNC
from corehq.apps.hqadmin.utils import get_celery_stats
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView, get_hqadmin_base_context
import six
from six.moves import filter


@require_superuser_or_contractor
def mass_email(request):
    if request.method == "POST":
        form = EmailForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['email_subject']
            html = form.cleaned_data['email_body_html']
            text = form.cleaned_data['email_body_text']
            real_email = form.cleaned_data['real_email']
            send_mass_emails.delay(request.couch_user.username, real_email, subject, html, text)
            messages.success(request, 'Task started. You will receive an email summarizing the results.')
        else:
            messages.error(request, 'Something went wrong, see below.')
    else:
        form = EmailForm()

    context = get_hqadmin_base_context(request)
    context['hide_filters'] = True
    context['form'] = form
    return render(request, "hqadmin/mass_email.html", context)


class CallcenterUCRCheck(BaseAdminSectionView):
    urlname = 'callcenter_ucr_check'
    page_title = ugettext_lazy("Check Callcenter UCR tables")
    template_name = "hqadmin/call_center_ucr_check.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(CallcenterUCRCheck, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        from corehq.apps.callcenter.data_source import get_call_center_domains
        from corehq.apps.callcenter.checks import get_call_center_data_source_stats

        if 'domain' not in self.request.GET:
            return {}

        domain = self.request.GET.get('domain', None)
        if domain:
            domains = [domain]
        else:
            domains = [dom.name for dom in get_call_center_domains() if dom.use_fixtures]

        domain_stats = get_call_center_data_source_stats(domains)

        context = {
            'data': sorted(list(domain_stats.values()), key=lambda s: s.name),
            'domain': domain
        }

        return context


@require_superuser
def callcenter_test(request):
    user_id = request.GET.get("user_id")
    date_param = request.GET.get("date")
    enable_caching = request.GET.get('cache')
    doc_id = request.GET.get('doc_id')

    if not user_id and not doc_id:
        return render(request, "hqadmin/callcenter_test.html", {"enable_caching": enable_caching})

    error = None
    user = None
    user_case = None
    domain = None
    if user_id:
        try:
            user = CommCareUser.get(user_id)
            domain = user.project
        except ResourceNotFound:
            error = "User Not Found"
    elif doc_id:
        try:
            doc = CommCareUser.get_db().get(doc_id)
            domain = Domain.get_by_name(doc['domain'])
            doc_type = doc.get('doc_type', None)
            if doc_type == 'CommCareUser':
                case_type = domain.call_center_config.case_type
                user_case = CaseAccessors(doc['domain']).get_case_by_domain_hq_user_id(doc['_id'], case_type)
            elif doc_type == 'CommCareCase':
                if doc.get('hq_user_id'):
                    user_case = CommCareCase.wrap(doc)
                else:
                    error = 'Case ID does does not refer to a Call Center Case'
        except ResourceNotFound:
            error = "User Not Found"

    try:
        query_date = dateutil.parser.parse(date_param)
    except ValueError:
        error = "Unable to parse date, using today"
        query_date = date.today()

    def view_data(case_id, indicators):
        new_dict = OrderedDict()
        key_list = sorted(indicators)
        for key in key_list:
            new_dict[key] = indicators[key]
        return {
            'indicators': new_dict,
            'case': CommCareCase.get(case_id),
        }

    if user or user_case:
        custom_cache = None if enable_caching else cache.caches['dummy']
        override_case = CallCenterCase.from_case(user_case)
        cci = CallCenterIndicators(
            domain.name,
            domain.default_timezone,
            domain.call_center_config.case_type,
            user,
            custom_cache=custom_cache,
            override_date=query_date,
            override_cases=[override_case] if override_case else None
        )
        data = {case_id: view_data(case_id, values) for case_id, values in cci.get_data().items()}
    else:
        data = {}

    context = {
        "error": error,
        "mobile_user": user,
        "date": json_format_date(query_date),
        "enable_caching": enable_caching,
        "data": data,
        "doc_id": doc_id
    }
    return render(request, "hqadmin/callcenter_test.html", context)


class ReprocessMessagingCaseUpdatesView(BaseAdminSectionView):
    urlname = 'reprocess_messaging_case_updates'
    page_title = ugettext_lazy("Reprocess Messaging Case Updates")
    template_name = 'hqadmin/messaging_case_updates.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(ReprocessMessagingCaseUpdatesView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return ReprocessMessagingCaseUpdatesForm(self.request.POST)
        return ReprocessMessagingCaseUpdatesForm()

    @property
    def page_context(self):
        context = get_hqadmin_base_context(self.request)
        context.update({
            'form': self.form,
        })
        return context

    def get_case(self, case_id):
        try:
            return CaseAccessorSQL.get_case(case_id)
        except CaseNotFound:
            pass

        try:
            return CaseAccessorCouch.get_case(case_id)
        except ResourceNotFound:
            pass

        return None

    def post(self, request, *args, **kwargs):
        from corehq.messaging.signals import messaging_case_changed_receiver

        if self.form.is_valid():
            case_ids = self.form.cleaned_data['case_ids']
            case_ids_not_processed = []
            case_ids_processed = []
            for case_id in case_ids:
                case = self.get_case(case_id)
                if not case or case.doc_type != 'CommCareCase':
                    case_ids_not_processed.append(case_id)
                else:
                    messaging_case_changed_receiver(None, case)
                    case_ids_processed.append(case_id)

            if case_ids_processed:
                messages.success(self.request,
                    _("Processed the following case ids: {}").format(','.join(case_ids_processed)))

            if case_ids_not_processed:
                messages.error(self.request,
                    _("Could not find cases belonging to these case ids: {}")
                    .format(','.join(case_ids_not_processed)))

        return self.get(request, *args, **kwargs)
