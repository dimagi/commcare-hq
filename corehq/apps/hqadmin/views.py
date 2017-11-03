import HTMLParser
import json
import socket
import uuid
from StringIO import StringIO
from collections import defaultdict, namedtuple, OrderedDict
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
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.callcenter.utils import CallCenterCase
from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.data_analytics.const import GIR_FIELDS
from corehq.apps.data_analytics.models import MALTRow, GIRRow
from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_developer,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.domain.models import Domain
from corehq.apps.es import filters
from corehq.apps.es.domains import DomainES
from corehq.apps.hqadmin.reporting.exceptions import HistoTypeNotFoundException
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
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_all_pillows_json, get_pillow_json, get_pillow_config_by_name
from . import service_checks, escheck
from .forms import (
    AuthenticateAsForm, BrokenBuildsForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)
from .history import get_recent_changes, download_changes
from .models import HqDeploy
from .reporting.reports import get_project_spaces, get_stats_data, HISTO_TYPE_TO_FUNC
from .utils import get_celery_stats


@require_superuser
def default(request):
    return HttpResponseRedirect(reverse('admin_report_dispatcher', args=('domains',)))

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=30,
)


def get_rabbitmq_management_url():
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://','').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        return "http://%s" % mq_management_url.split('@')[-1]
    else:
        return None


def get_hqadmin_base_context(request):
    return {
        "domain": None,
    }


class BaseAdminSectionView(BaseSectionPageView):
    section_name = ugettext_lazy("Admin Reports")

    @property
    def section_url(self):
        return reverse('default_admin_report')

    @property
    def page_url(self):
        return reverse(self.urlname)


class AuthenticateAs(BaseAdminSectionView):
    urlname = 'authenticate_as'
    page_title = _("Login as Other User")
    template_name = 'hqadmin/authenticate_as.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(AuthenticateAs, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        return {
            'hide_filters': True,
            'form': AuthenticateAsForm(initial=self.kwargs)
        }

    def post(self, request, *args, **kwargs):
        form = AuthenticateAsForm(self.request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            request.user = User.objects.get(username=username)

            # http://stackoverflow.com/a/2787747/835696
            # This allows us to bypass the authenticate call
            request.user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, request.user)
            return HttpResponseRedirect('/')
        return self.get(request, *args, **kwargs)


class SuperuserManagement(BaseAdminSectionView):
    urlname = 'superuser_management'
    page_title = _("Grant or revoke superuser access")
    template_name = 'hqadmin/superuser_management.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(SuperuserManagement, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        # only staff can toggle is_staff
        can_toggle_is_staff = self.request.user.is_staff
        # render validation errors if rendered after POST
        args = [can_toggle_is_staff, self.request.POST] if self.request.POST else [can_toggle_is_staff]
        return {
            'form': SuperuserManagementForm(*args)
        }

    def post(self, request, *args, **kwargs):
        can_toggle_is_staff = request.user.is_staff
        form = SuperuserManagementForm(can_toggle_is_staff, self.request.POST)
        if form.is_valid():
            users = form.cleaned_data['users']
            is_superuser = 'is_superuser' in form.cleaned_data['privileges']
            is_staff = 'is_staff' in form.cleaned_data['privileges']

            for user in users:
                # save user object only if needed and just once
                should_save = False
                if user.is_superuser is not is_superuser:
                    user.is_superuser = is_superuser
                    should_save = True

                if can_toggle_is_staff and user.is_staff is not is_staff:
                    user.is_staff = is_staff
                    should_save = True

                if should_save:
                    user.save()
            messages.success(request, _("Successfully updated superuser permissions"))

        return self.get(request, *args, **kwargs)


class RecentCouchChangesView(BaseAdminSectionView):
    urlname = 'view_recent_changes'
    template_name = 'hqadmin/couch_changes.html'
    page_title = ugettext_lazy("Recent Couch Changes")

    @use_nvd3_v3
    @use_datatables
    @use_jquery_ui
    @method_decorator(require_superuser_or_developer)
    def dispatch(self, *args, **kwargs):
        return super(RecentCouchChangesView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        count = int(self.request.GET.get('changes', 1000))
        changes = list(get_recent_changes(get_db(), count))
        domain_counts = defaultdict(lambda: 0)
        doc_type_counts = defaultdict(lambda: 0)
        for change in changes:
            domain_counts[change['domain']] += 1
            doc_type_counts[change['doc_type']] += 1

        def _to_chart_data(data_dict):
            return [
                {'label': l, 'value': v} for l, v in sorted(data_dict.items(), key=lambda tup: tup[1], reverse=True)
            ][:20]

        return {
            'count': count,
            'recent_changes': changes,
            'domain_data': {'key': 'domains', 'values': _to_chart_data(domain_counts)},
            'doc_type_data': {'key': 'doc types', 'values': _to_chart_data(doc_type_counts)},
        }


@require_superuser_or_developer
def download_recent_changes(request):
    count = int(request.GET.get('changes', 10000))
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="recent_changes.csv"'
    download_changes(get_db(), count, resp)
    return resp


@require_superuser_or_developer
def system_ajax(request):
    """
    Utility ajax functions for polling couch and celerymon
    """
    type = request.GET.get('api', None)
    task_limit = getattr(settings, 'CELERYMON_TASK_LIMIT', 12)
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    db = XFormInstance.get_db()
    if type == "_active_tasks":
        try:
            tasks = filter(lambda x: x['type'] == "indexer", db.server.active_tasks())
        except Unauthorized:
            return json_response({'error': "Unable to access CouchDB Tasks (unauthorized)."}, status_code=500)

        if not is_bigcouch():
            return json_response(tasks)
        else:
            # group tasks by design doc
            task_map = defaultdict(dict)
            for task in tasks:
                meta = task_map[task['design_document']]
                tasks = meta.get('tasks', [])
                tasks.append(task)
                meta['tasks'] = tasks

            design_docs = []
            for dd, meta in task_map.items():
                meta['design_document'] = dd[len('_design/'):]
                total_changes = sum(task['total_changes'] for task in meta['tasks'])
                for task in meta['tasks']:
                    task['progress_contribution'] = task['changes_done'] * 100 / total_changes

                design_docs.append(meta)
            return json_response(design_docs)
    elif type == "_stats":
        return json_response({})
    elif type == "_logs":
        pass
    elif type == 'pillowtop':
        pillow_meta = get_all_pillows_json()
        supervisor_status = all_pillows_supervisor_status([meta['name'] for meta in pillow_meta])
        for meta in pillow_meta:
            meta.update(supervisor_status[meta['name']])
        return json_response(sorted(pillow_meta, key=lambda m: m['name'].lower()))
    elif type == 'stale_pillows':
        es_index_status = [
            escheck.check_case_es_index(interval=3),
            escheck.check_xform_es_index(interval=3),
            escheck.check_reportcase_es_index(interval=3),
            escheck.check_reportxform_es_index(interval=3)
        ]
        return json_response(es_index_status)

    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        if type == "flower_poll":
            ret = []
            try:
                t = cresource.get("api/tasks", params_dict={'limit': task_limit}).body_string()
                all_tasks = json.loads(t)
            except Exception as ex:
                return json_response({'error': "Error with getting from celery_flower: %s" % ex}, status_code=500)

            for task_id, traw in all_tasks.items():
                # it's an array of arrays - looping through [<id>, {task_info_dict}]
                if 'name' in traw and traw['name']:
                    traw['name'] = '.'.join(traw['name'].split('.')[-2:])
                else:
                    traw['name'] = None
                ret.append(traw)
            ret = sorted(ret, key=lambda x: x['succeeded'], reverse=True)
            return HttpResponse(json.dumps(ret), content_type='application/json')
    return HttpResponse('{}', content_type='application/json')


@require_superuser_or_developer
def check_services(request):

    def run_test(service_name, test):
        try:
            result = test()
        except Exception as e:
            status = "EXCEPTION"
            msg = repr(e)
        else:
            status = "SUCCESS" if result.success else "FAILURE"
            msg = result.msg
        return "{} {}: {}<br/>".format(status, service_name, msg)

    results = [run_test(service_name, test) for service_name, test in service_checks.CHECKS.items()]
    return HttpResponse("<pre>" + "".join(results) + "</pre>")


class SystemInfoView(BaseAdminSectionView):
    page_title = ugettext_lazy("System Info")
    urlname = 'system_info'
    template_name = "hqadmin/system_info.html"

    @use_datatables
    @use_jquery_ui
    @method_decorator(require_superuser_or_developer)
    def dispatch(self, request, *args, **kwargs):
        return super(SystemInfoView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        environment = settings.SERVER_ENVIRONMENT

        context = get_hqadmin_base_context(self.request)
        context['couch_update'] = self.request.GET.get('couch_update', 5000)
        context['celery_update'] = self.request.GET.get('celery_update', 10000)
        context['db_update'] = self.request.GET.get('db_update', 30000)
        context['self.request'] = getattr(settings, 'CELERY_FLOWER_URL', None)

        context['is_bigcouch'] = is_bigcouch()
        context['rabbitmq_url'] = get_rabbitmq_management_url()
        context['hide_filters'] = True
        context['current_system'] = socket.gethostname()
        context['deploy_history'] = HqDeploy.get_latest(environment, limit=5)

        context['user_is_support'] = hasattr(self.request, 'user') and SUPPORT.enabled(self.request.user.username)

        context['redis'] = service_checks.check_redis()
        context['rabbitmq'] = service_checks.check_rabbitmq()
        context['celery_stats'] = get_celery_stats()
        context['heartbeat'] = service_checks.check_heartbeat()

        context['cluster_health'] = escheck.check_es_cluster_health()

        return context


@require_POST
@require_superuser_or_developer
def pillow_operation_api(request):
    pillow_name = request.POST["pillow_name"]
    operation = request.POST["operation"]
    try:
        pillow_config = get_pillow_config_by_name(pillow_name)
        pillow = pillow_config.get_instance()
    except PillowNotFoundError:
        pillow_config = None
        pillow = None

    def get_response(error=None):
        response = {
            'pillow_name': pillow_name,
            'operation': operation,
            'success': error is None,
            'message': error,
        }
        response.update(pillow_supervisor_status(pillow_name))
        if pillow_config:
            response.update(get_pillow_json(pillow_config))
        return json_response(response)

    @any_toggle_enabled(SUPPORT)
    def reset_pillow(request):
        pillow.reset_checkpoint()
        if PillowtopSupervisorApi().restart_pillow(pillow_name):
            return get_response()
        else:
            return get_response("Checkpoint reset but failed to restart pillow. "
                                "Restart manually to complete reset.")

    @any_toggle_enabled(SUPPORT)
    def start_pillow(request):
        if PillowtopSupervisorApi().start_pillow(pillow_name):
            return get_response()
        else:
            return get_response('Unknown error')

    @any_toggle_enabled(SUPPORT)
    def stop_pillow(request):
        if PillowtopSupervisorApi().stop_pillow(pillow_name):
            return get_response()
        else:
            return get_response('Unknown error')

    if pillow:
        try:
            if operation == 'reset_checkpoint':
                reset_pillow(request)
            if operation == 'start':
                start_pillow(request)
            if operation == 'stop':
                stop_pillow(request)
            if operation == 'refresh':
                return get_response()
        except SupervisorException as e:
            return get_response(str(e))
    else:
        return get_response("No pillow found with name '{}'".format(pillow_name))


class AdminRestoreView(TemplateView):
    template_name = 'hqadmin/admin_restore.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(AdminRestoreView, self).dispatch(request, *args, **kwargs)

    def _validate_user_access(self, user):
        return True

    def get(self, request, *args, **kwargs):
        full_username = request.GET.get('as', '')
        if not full_username or '@' not in full_username:
            return HttpResponseBadRequest('Please specify a user using ?as=user@domain')

        username, domain = full_username.split('@')
        if not domain.endswith(settings.HQ_ACCOUNT_ROOT):
            full_username = format_username(username, domain)

        self.user = CommCareUser.get_by_username(full_username)
        if not self.user:
            return HttpResponseNotFound('User %s not found.' % full_username)

        if not self._validate_user_access(self.user):
            raise Http404()

        self.app_id = kwargs.get('app_id', None)

        raw = request.GET.get('raw') == 'true'
        if raw:
            response, _ = self._get_restore_response()
            return response

        download = request.GET.get('download') == 'true'
        if download:
            response, _ = self._get_restore_response()
            response['Content-Disposition'] = "attachment; filename={}-restore.xml".format(username)
            return response

        return super(AdminRestoreView, self).get(request, *args, **kwargs)

    def _get_restore_response(self):
        return get_restore_response(
            self.user.domain, self.user, app_id=self.app_id,
            **get_restore_params(self.request)
        )

    def get_context_data(self, **kwargs):
        context = super(AdminRestoreView, self).get_context_data(**kwargs)
        response, timing_context = self._get_restore_response()
        timing_context = timing_context or TimingContext(self.user.username)
        if isinstance(response, StreamingHttpResponse):
            string_payload = ''.join(response.streaming_content)
            xml_payload = etree.fromstring(string_payload)
            restore_id_element = xml_payload.find('{{{0}}}Sync/{{{0}}}restore_id'.format(SYNC_XMLNS))
            num_cases = len(xml_payload.findall('{http://commcarehq.org/case/transaction/v2}case'))
            num_locations = len(
                xml_payload.findall("{{{0}}}fixture[@id='locations']/{{{0}}}locations/{{{0}}}location"
                                    .format(RESPONSE_XMLNS)))
        else:
            if response.status_code in (401, 404):
                # corehq.apps.ota.views.get_restore_response couldn't find user or user didn't have perms
                xml_payload = E.error(response.content)
            elif response.status_code == 412:
                # RestoreConfig.get_response returned HttpResponse 412. Response content is already XML
                xml_payload = etree.fromstring(response.content)
            else:
                message = _('Unexpected restore response {}: {}. '
                            'If you believe this is a bug please report an issue.').format(response.status_code,
                                                                                           response.content)
                xml_payload = E.error(message)
            restore_id_element = None
            num_cases = 0
            num_locations = 0
        formatted_payload = etree.tostring(xml_payload, pretty_print=True)
        context.update({
            'payload': formatted_payload,
            'restore_id': restore_id_element.text if restore_id_element is not None else None,
            'status_code': response.status_code,
            'timing_data': timing_context.to_list(),
            'num_cases': num_cases,
            'num_locations': num_locations,
        })
        return context


class DomainAdminRestoreView(AdminRestoreView):
    urlname = 'domain_admin_restore'

    def dispatch(self, request, *args, **kwargs):
        return TemplateView.dispatch(self, request, *args, **kwargs)

    @method_decorator(login_or_basic)
    @method_decorator(domain_admin_required)
    def get(self, request, domain, **kwargs):
        self.domain = domain
        return super(DomainAdminRestoreView, self).get(request, **kwargs)

    def _validate_user_access(self, user):
        return self.domain == user.domain


@require_POST
@require_superuser
def run_command(request):
    cmd = request.POST.get('command')
    if cmd not in ['remove_duplicate_domains']: # only expose this one command for now
        return json_response({"success": False, "output": "Command not available"})

    output_buf = StringIO()
    management.call_command(cmd, stdout=output_buf)
    output = output_buf.getvalue()
    output_buf.close()

    return json_response({"success": True, "output": output})


class FlagBrokenBuilds(FormView):
    template_name = "hqadmin/flag_broken_builds.html"
    form_class = BrokenBuildsForm

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(FlagBrokenBuilds, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        db = ApplicationBase.get_db()
        build_jsons = db.all_docs(keys=form.build_ids, include_docs=True)
        docs = []
        for doc in [build_json['doc'] for build_json in build_jsons.all()]:
            if doc.get('doc_type') in ['Application', 'RemoteApp']:
                doc['build_broken'] = True
                docs.append(doc)
        db.bulk_save(docs)
        return HttpResponse("posted!")


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=90)
def stats_data(request):
    histo_type = request.GET.get('histogram_type')
    interval = request.GET.get("interval", "week")
    datefield = request.GET.get("datefield")
    get_request_params_json = request.GET.get("get_request_params", None)
    get_request_params = (
        json.loads(HTMLParser.HTMLParser().unescape(get_request_params_json))
        if get_request_params_json is not None else {}
    )

    stats_kwargs = {
        k: get_request_params[k]
        for k in get_request_params if k != "domain_params_es"
    }
    if datefield is not None:
        stats_kwargs['datefield'] = datefield

    domain_params_es = get_request_params.get("domain_params_es", {})

    if not request.GET.get("enddate"):  # datespan should include up to the current day when unspecified
        request.datespan.enddate += timedelta(days=1)

    domain_params, __ = parse_args_for_es(request, prefix='es_')
    domain_params.update(domain_params_es)

    domains = get_project_spaces(facets=domain_params)

    try:
        return json_response(get_stats_data(
            histo_type,
            domains,
            request.datespan,
            interval,
            **stats_kwargs
        ))
    except HistoTypeNotFoundException:
        return HttpResponseBadRequest(
            'histogram_type param must be one of <ul><li>{}</li></ul>'
            .format('</li><li>'.join(HISTO_TYPE_TO_FUNC.keys())))


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
def admin_reports_stats_data(request):
    return stats_data(request)


class _Db(object):
    """
    Light wrapper for providing interface like Couchdbkit's Database objects.
    """

    def __init__(self, dbname, getter, doc_type):
        self.dbname = dbname
        self._getter = getter
        self.doc_type = doc_type

    def get(self, record_id):
        try:
            return self._getter(record_id)
        except (XFormNotFound, CaseNotFound, ObjectDoesNotExist):
            raise ResourceNotFound("missing")


_SQL_DBS = OrderedDict((db.dbname, db) for db in [
    _Db(
        XFormInstanceSQL._meta.db_table,
        lambda id_: XFormInstanceSQLRawDocSerializer(XFormInstanceSQL.get_obj_by_id(id_)).data,
        XFormInstanceSQL.__name__
    ),
    _Db(
        CommCareCaseSQL._meta.db_table,
        lambda id_: CommCareCaseSQLRawDocSerializer(CommCareCaseSQL.get_obj_by_id(id_)).data,
        CommCareCaseSQL.__name__
    ),
    _Db(
        SQLLocation._meta.db_table,
        lambda id_: SQLLocation.objects.get(location_id=id_).to_json(),
        SQLLocation.__name__
    ),
])


def _get_db_from_db_name(db_name):
    if db_name in _SQL_DBS:
        return _SQL_DBS[db_name]
    elif db_name == couch_config.get_db(None).dbname:  # primary db
        return couch_config.get_db(None)
    else:
        return couch_config.get_db(db_name)


def _lookup_id_in_database(doc_id, db_name=None):
    db_result = namedtuple('db_result', 'dbname result status')
    STATUSES = defaultdict(lambda: 'warning', {
        'missing': 'default',
        'deleted': 'danger',
    })

    response = {"doc_id": doc_id}
    if db_name:
        dbs = [_get_db_from_db_name(db_name)]
        response['selected_db'] = db_name
    else:
        couch_dbs = couch_config.all_dbs_by_slug.values()
        sql_dbs = _SQL_DBS.values()
        dbs = couch_dbs + sql_dbs

    db_results = []
    for db in dbs:
        try:
            doc = db.get(doc_id)
        except ResourceNotFound as e:
            db_results.append(db_result(db.dbname, e.msg, STATUSES[e.msg]))
        else:
            db_results.append(db_result(db.dbname, 'found', 'success'))
            response.update({
                "doc": json.dumps(doc, indent=4, sort_keys=True),
                "doc_type": doc.get('doc_type', getattr(db, 'doc_type', 'Unknown')),
                "dbname": db.dbname,
            })

    response['db_results'] = db_results
    return response


@require_superuser
def web_user_lookup(request):
    template = "hqadmin/web_user_lookup.html"
    web_user_email = request.GET.get("q")
    if not web_user_email:
        return render(request, template, {})

    web_user = WebUser.get_by_username(web_user_email)
    context = {
        'audit_report_url': reverse('admin_report_dispatcher', args=('user_audit_report',))
    }
    if web_user is None:
        messages.error(
            request, u"Sorry, no user found with email {}. Did you enter it correctly?".format(web_user_email)
        )
    else:
        from django_otp import user_has_device
        context['web_user'] = web_user
        django_user = web_user.get_django_user()
        context['has_two_factor'] = user_has_device(django_user)
    return render(request, template, context)


@method_decorator(require_superuser, name='dispatch')
class DisableUserView(FormView):
    template_name = 'hqadmin/disable_user.html'
    success_url = None
    form_class = DisableUserForm
    urlname = 'disable_user'

    def get_initial(self):
        return {
            'user': self.user,
            'reset_password': False,
        }

    @property
    def username(self):
        return self.request.GET.get("username")

    @cached_property
    def user(self):
        try:
            return User.objects.get(username__iexact=self.username)
        except User.DoesNotExist:
            return None

    @property
    def redirect_url(self):
        return '{}?q={}'.format(reverse('web_user_lookup'), self.username)

    def get(self, request, *args, **kwargs):
        if not self.user:
            return self.redirect_response(request)

        return super(DisableUserView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(DisableUserView, self).get_context_data(**kwargs)
        context['verb'] = 'disable' if self.user.is_active else 'enable'
        context['username'] = self.username
        return context

    def redirect_response(self, request):
        messages.warning(request, _('User with username %(username)s not found.') % {
            'username': self.username
        })
        return redirect(self.redirect_url)

    def form_valid(self, form):
        if not self.user:
            return self.redirect_response(self.request)

        reset_password = form.cleaned_data['reset_password']
        if reset_password:
            self.user.set_password(uuid.uuid4().hex)

        # toggle active state
        self.user.is_active = not self.user.is_active
        self.user.save()

        verb = 're-enabled' if self.user.is_active else 'disabled'
        mail_admins(
            "User account {}".format(verb),
            "The following user account has been {verb}: \n"
            "    Account: {username}\n"
            "    Reset by: {reset_by}\n"
            "    Password reset: {password_reset}\n"
            "    Reason: {reason}".format(
                verb=verb,
                username=self.username,
                reset_by=self.request.user.username,
                password_reset=str(reset_password),
                reason=form.cleaned_data['reason'],
            )
        )
        send_HTML_email(
            "%sYour account has been %s" % (settings.EMAIL_SUBJECT_PREFIX, verb),
            self.username,
            render_to_string('hqadmin/email/account_disabled_email.html', context={
                'support_email': settings.SUPPORT_EMAIL,
                'password_reset': reset_password,
                'user': self.user,
                'verb': verb,
                'reason': form.cleaned_data['reason'],
            }),
        )

        messages.success(self.request, _('Account successfully %(verb)s.' % {'verb': verb}))
        return redirect('{}?q={}'.format(reverse('web_user_lookup'), self.username))


@method_decorator(require_superuser, name='dispatch')
class DisableTwoFactorView(FormView):
    """
    View for disabling two-factor for a user's account.
    """
    template_name = 'hqadmin/disable_two_factor.html'
    success_url = None
    form_class = DisableTwoFactorForm
    urlname = 'disable_two_factor'

    def get_initial(self):
        return {
            'username': self.request.GET.get("q"),
            'disable_for_days': 0,
        }

    def get(self, request, *args, **kwargs):
        from django_otp import user_has_device

        username = request.GET.get("q")
        redirect_url = '{}?q={}'.format(reverse('web_user_lookup'), username)
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            messages.warning(request, _('User with username %(username)s not found.') % {
                'username': username
            })
            return redirect(redirect_url)

        if not user_has_device(user):
            messages.warning(request, _(
                'User with username %(username)s does not have Two-Factor Auth enabled.') % {
                'username': username
            })
            return redirect(redirect_url)

        return super(DisableTwoFactorView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        from django_otp import devices_for_user

        username = form.cleaned_data['username']
        user = User.objects.get(username__iexact=username)
        for device in devices_for_user(user):
            device.delete()

        disable_for_days = form.cleaned_data['disable_for_days']
        if disable_for_days:
            couch_user = CouchUser.from_django_user(user)
            disable_until = datetime.utcnow() + timedelta(days=disable_for_days)
            couch_user.two_factor_auth_disabled_until = disable_until
            couch_user.save()

        mail_admins(
            "Two-Factor account reset",
            "Two-Factor auth was reset. Details: \n"
            "    Account reset: {username}\n"
            "    Reset by: {reset_by}\n"
            "    Request Verificatoin Mode: {verification}\n"
            "    Verified by: {verified_by}\n"
            "    Two-Factor disabled for {days} days.".format(
                username=username,
                reset_by=self.request.user.username,
                verification=form.cleaned_data['verification_mode'],
                verified_by=form.cleaned_data['via_who'] or self.request.user.username,
                days=disable_for_days
            ),
        )
        send_HTML_email(
            "%sTwo-Factor authentication reset" % settings.EMAIL_SUBJECT_PREFIX,
            username,
            render_to_string('hqadmin/email/two_factor_reset_email.html', context={
                'until': disable_until.strftime('%Y-%m-%d %H:%M:%S UTC') if disable_for_days else None,
                'support_email': settings.SUPPORT_EMAIL,
                'email_subject': "[URGENT] Possible Account Breach",
                'email_body': "Two Factor Auth on my CommCare account "
                              "was disabled without my request. My username is: %s" % username,
            }),
        )

        messages.success(self.request, _('Two-Factor Auth successfully disabled.'))
        return redirect('{}?q={}'.format(reverse('web_user_lookup'), username))


@require_superuser
def doc_in_es(request):
    doc_id = request.GET.get("id")
    if not doc_id:
        return render(request, "hqadmin/doc_in_es.html", {})

    def to_json(doc):
        return json.dumps(doc, indent=4, sort_keys=True) if doc else "NOT FOUND!"

    query = {"filter": {"ids": {"values": [doc_id]}}}
    found_indices = {}
    es_doc_type = None
    for index in ES_META:
        res = run_query(index, query)
        if 'hits' in res and res['hits']['total'] == 1:
            es_doc = res['hits']['hits'][0]['_source']
            found_indices[index] = to_json(es_doc)
            es_doc_type = es_doc_type or es_doc.get('doc_type')

    context = {
        "doc_id": doc_id,
        "es_info": {
            "status": "found" if found_indices else "NOT FOUND IN ELASTICSEARCH!",
            "doc_type": es_doc_type,
            "found_indices": found_indices,
        },
        "couch_info": _lookup_id_in_database(doc_id),
    }
    return render(request, "hqadmin/doc_in_es.html", context)


@require_superuser
def raw_couch(request):
    get_params = dict(request.GET.iteritems())
    return HttpResponseRedirect(reverse("raw_doc", params=get_params))


@require_superuser
def raw_doc(request):
    doc_id = request.GET.get("id")
    db_name = request.GET.get("db_name", None)
    if db_name and "__" in db_name:
        db_name = db_name.split("__")[-1]
    context = _lookup_id_in_database(doc_id, db_name) if doc_id else {}

    if request.GET.get("raw", False):
        if 'doc' in context:
            return HttpResponse(context['doc'], content_type="application/json")
        else:
            return HttpResponse(json.dumps({"status": "missing"}),
                                content_type="application/json", status=404)

    other_couch_dbs = sorted(filter(None, couch_config.all_dbs_by_slug.keys()))
    context['all_databases'] = ['commcarehq'] + other_couch_dbs + _SQL_DBS.keys()
    context['use_code_mirror'] = request.GET.get('code_mirror', 'true').lower() == 'true'
    return render(request, "hqadmin/raw_couch.html", context)


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
        key_list = sorted(indicators.keys())
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


class DownloadMALTView(BaseAdminSectionView):
    urlname = 'download_malt'
    page_title = ugettext_lazy("Download MALT")
    template_name = "hqadmin/malt_downloader.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadMALTView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if 'year_month' in request.GET:
            try:
                year, month = request.GET['year_month'].split('-')
                year, month = int(year), int(month)
                return _malt_csv_response(month, year)
            except (ValueError, ValidationError):
                messages.error(
                    request,
                    _("Enter a valid year-month. e.g. 2015-09 (for September 2015)")
                )
        return super(DownloadMALTView, self).get(request, *args, **kwargs)


def _malt_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    queryset = MALTRow.objects.filter(month=query_month)
    return export_as_csv_action(exclude=['id'])(MALTRowAdmin, None, queryset)


class DownloadGIRView(BaseAdminSectionView):
    urlname = 'download_gir'
    page_title = ugettext_lazy("Download GIR")
    template_name = "hqadmin/gir_downloader.html"

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(DownloadGIRView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if 'year_month' in request.GET:
            try:
                year, month = request.GET['year_month'].split('-')
                year, month = int(year), int(month)
                return _gir_csv_response(month, year)
            except (ValueError, ValidationError):
                messages.error(
                    request,
                    _("Enter a valid year-month. e.g. 2015-09 (for September 2015)")
                )
        return super(DownloadGIRView, self).get(request, *args, **kwargs)


def _gir_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    prev_month_year, prev_month = add_months(year, month, -1)
    prev_month_string = "{year}-{month}-01".format(year=prev_month_year, month=prev_month)
    two_ago_year, two_ago_month = add_months(year, month, -2)
    two_ago_string = "{year}-{month}-01".format(year=two_ago_year, month=two_ago_month)
    if not GIRRow.objects.filter(month=query_month).exists():
        return HttpResponse('Sorry, that month is not yet available')
    queryset = GIRRow.objects.filter(month__in=[query_month, prev_month_string, two_ago_string]).order_by('-month')
    domain_months = defaultdict(list)
    for item in queryset:
        domain_months[item.domain_name].append(item)
    field_names = GIR_FIELDS
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = u'attachment; filename=gir.csv'
    writer = UnicodeWriter(response)
    writer.writerow(list(field_names))
    for months in domain_months.values():
        writer.writerow(months[0].export_row(months[1:]))
    return response


@require_superuser
def branches_on_staging(request, template='hqadmin/branches_on_staging.html'):
    branches = _get_branches_merged_into_autostaging()
    branches_by_submodule = [(None, branches)] + [
        (cwd, _get_branches_merged_into_autostaging(cwd))
        for cwd in _get_submodules()
    ]
    return render(request, template, {
        'branches_by_submodule': branches_by_submodule,
    })


def _get_branches_merged_into_autostaging(cwd=None):
    import sh
    git = sh.git.bake(_tty_out=False, _cwd=cwd)
    # %p %s is parent hashes + subject of commit message, which will look like:
    # <merge base> <merge head> Merge <stuff> into autostaging
    try:
        pipe = git.log('origin/master...', grep='Merge .* into autostaging', format='%p %s')
    except sh.ErrorReturnCode_128:
        # when origin/master isn't fetched, you'll get
        #   fatal: ambiguous argument 'origin/master...': \
        #   unknown revision or path not in the working tree.
        git.fetch()
        return _get_branches_merged_into_autostaging(cwd=cwd)
    CommitBranchPair = namedtuple('CommitBranchPair', ['commit', 'branch'])
    return sorted(
        (CommitBranchPair(
            *line.strip()
            .replace("Merge remote-tracking branch 'origin/", '')
            .replace("Merge branch '", '')
            .replace("' into autostaging", '')
            .split(' ')[1:]
        ) for line in pipe),
        key=lambda pair: pair.branch
    )


def _get_submodules():
    """
    returns something like
    ['corehq/apps/hqmedia/static/hqmedia/MediaUploader',
     'corehq/apps/prelogin',
     'submodules/auditcare-src',
     ...]
    """
    import sh
    git = sh.git.bake(_tty_out=False)
    return [
        line.strip()[1:].split()[1]
        for line in git.submodule()
    ]


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
            'data': sorted(domain_stats.values(), key=lambda s: s.name),
            'domain': domain
        }

        return context


class DimagisphereView(TemplateView):

    def get_context_data(self, **kwargs):
        context = super(DimagisphereView, self).get_context_data(**kwargs)
        context['tvmode'] = 'tvmode' in self.request.GET
        return context


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


def top_five_projects_by_country(request):
    data = {}
    internalMode = request.user.is_superuser
    attributes = ['internal.area', 'internal.sub_area', 'cp_n_active_cc_users', 'deployment.countries']

    if internalMode:
        attributes = ['name', 'internal.organization_name', 'internal.notes'] + attributes

    if 'country' in request.GET:
        country = request.GET.get('country')
        projects = (DomainES().is_active_project().real_domains()
                    .filter(filters.term('deployment.countries', country))
                    .sort('cp_n_active_cc_users', True).source(attributes).size(5).run().hits)
        data = {country: projects, 'internal': internalMode}

    return json_response(data)


class WebUserDataView(View):
    urlname = 'web_user_data'

    @method_decorator(check_lockout)
    @method_decorator(basicauth())
    def get(self, request, *args, **kwargs):
        couch_user = CouchUser.from_django_user(request.user)
        if couch_user.is_web_user():
            data = {'domains': couch_user.domains}
            return JsonResponse(data)
        else:
            return HttpResponse('Only web users can access this endpoint', status=400)
