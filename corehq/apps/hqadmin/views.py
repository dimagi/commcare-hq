import HTMLParser
import json
import socket
from datetime import timedelta, date
from collections import defaultdict
from StringIO import StringIO

import dateutil
from django.utils.datastructures import SortedDict
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.core import management, cache
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.views.generic import FormView
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
)
from restkit import Resource
from restkit.errors import Unauthorized
from couchdbkit import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from corehq.apps.callcenter.indicator_sets import CallCenterIndicators
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.style.decorators import use_datatables, use_jquery_ui
from corehq.apps.style.views import BaseB3SectionPageView
from corehq.toggles import any_toggle_enabled, SUPPORT
from corehq.util.couchdb_management import couch_config
from corehq.util.supervisord.api import PillowtopSupervisorApi, SupervisorException, all_pillows_supervisor_status, \
    pillow_supervisor_status
from couchforms.models import XFormInstance
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_all_pillows_json, get_pillow_json, get_pillow_config_by_name
from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.data_analytics.admin import MALTRowAdmin
from corehq.apps.hqadmin.history import get_recent_changes, download_changes
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.forms import BrokenBuildsForm
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.domain.decorators import require_superuser, require_superuser_or_developer
from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.escheck import (
    check_es_cluster_health,
    check_xform_es_index,
    check_reportcase_es_index,
    check_case_es_index,
    check_reportxform_es_index
)
from corehq.apps.hqadmin.system_info.checks import check_redis, check_rabbitmq, check_celery_health
from corehq.apps.hqadmin.reporting.reports import (
    get_project_spaces,
    get_stats_data,
)
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.reports.graph_models import Axis, LineChart
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username
from corehq.sql_db.connections import Session
from corehq.elastic import parse_args_for_es, run_query, ES_META
from dimagi.utils.couch.database import get_db, is_bigcouch
from dimagi.utils.django.management import export_as_csv_action
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.parsing import json_format_date
from dimagi.utils.web import json_response
from .multimech import GlobalConfig
from .forms import AuthenticateAsForm


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


class BaseAdminSectionView(BaseB3SectionPageView):
    section_name = ugettext_lazy("Admin Reports")

    @property
    def section_url(self):
        return reverse('default_admin_report')

    @property
    def page_url(self):
        return reverse(self.urlname)


class AuthenticateAs(BasePageView):
    urlname = 'authenticate_as'
    page_title = _("Login as other user")
    template_name = 'hqadmin/authenticate_as.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(AuthenticateAs, self).dispatch(*args, **kwargs)

    def page_url(self):
        return reverse(self.urlname)

    def get_context_data(self, **kwargs):
        context = super(AuthenticateAs, self).get_context_data(**kwargs)
        context.update({
            'hide_filters': True,
            'page_url': self.page_url(),
            'form': AuthenticateAsForm(initial=kwargs)
        })
        return context

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


@require_superuser_or_developer
def view_recent_changes(request):
    count = int(request.GET.get('changes', 1000))
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

    return render(request, 'hqadmin/couch_changes.html', {
        'count': count,
        'recent_changes': changes,
        'domain_data': {'key': 'domains', 'values': _to_chart_data(domain_counts)},
        'doc_type_data': {'key': 'doc types', 'values': _to_chart_data(doc_type_counts)},
        'hide_filters': True,
    })


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
        return json_response(sorted(pillow_meta, key=lambda m: m['name']))
    elif type == 'stale_pillows':
        es_index_status = [
            check_case_es_index(interval=3),
            check_xform_es_index(interval=3),
            check_reportcase_es_index(interval=3),
            check_reportxform_es_index(interval=3)
        ]
        return json_response(es_index_status)

    if celery_monitoring:
        cresource = Resource(celery_monitoring, timeout=3)
        if type == "flower_poll":
            ret = []
            try:
                t = cresource.get("api/tasks", params_dict={'limit': task_limit}).body_string()
                all_tasks = json.loads(t)
            except Exception, ex:
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


class SystemInfoView(BaseAdminSectionView):
    page_title = ugettext_lazy("System Info")
    urlname = 'system_info'
    template_name = "hqadmin/system_info.html"

    @use_datatables
    @use_jquery_ui
    @method_decorator(require_superuser_or_developer)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseAdminSectionView, self).dispatch(request, *args, **kwargs)

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

        context.update(check_redis())
        context.update(check_rabbitmq())
        context.update(check_celery_health())
        context.update(check_es_cluster_health())

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
        if supervisor.restart_pillow(pillow_name):
            return get_response()
        else:
            return get_response("Checkpoint reset but failed to restart pillow. "
                                "Restart manually to complete reset.")

    @any_toggle_enabled(SUPPORT)
    def start_pillow(request):
        if supervisor.start_pillow(pillow_name):
            return get_response()
        else:
            return get_response('Unknown error')

    @any_toggle_enabled(SUPPORT)
    def stop_pillow(request):
        if supervisor.stop_pillow(pillow_name):
            return get_response()
        else:
            return get_response('Unknown error')

    if pillow:
        try:
            supervisor = PillowtopSupervisorApi()
        except Exception as e:
            return get_response(str(e))

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


@require_superuser
@require_GET
def admin_restore(request, app_id=None):
    full_username = request.GET.get('as', '')
    if not full_username or '@' not in full_username:
        return HttpResponseBadRequest('Please specify a user using ?as=user@domain')

    username, domain = full_username.split('@')
    if not domain.endswith(settings.HQ_ACCOUNT_ROOT):
        full_username = format_username(username, domain)

    user = CommCareUser.get_by_username(full_username)
    if not user:
        return HttpResponseNotFound('User %s not found.' % full_username)

    overwrite_cache = request.GET.get('ignore_cache') == 'true'
    return get_restore_response(user.domain, user, overwrite_cache=overwrite_cache, app_id=app_id,
                                **get_restore_params(request))

@require_superuser
def management_commands(request, template="hqadmin/management_commands.html"):
    commands = [(_('Remove Duplicate Domains'), 'remove_duplicate_domains')]
    context = get_hqadmin_base_context(request)
    context["hide_filters"] = True
    context["commands"] = commands
    return render(request, template, context)


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
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
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

    return json_response(get_stats_data(
        histo_type,
        domains,
        request.datespan,
        interval,
        **stats_kwargs
    ))


@require_superuser
@datespan_in_request(from_param="startdate", to_param="enddate", default_days=365)
def admin_reports_stats_data(request):
    return stats_data(request)


@require_superuser
def loadtest(request):
    # The multimech results api is kinda all over the place.
    # the docs are here: http://testutils.org/multi-mechanize/datastore.html

    scripts = ['submit_form.py', 'ota_restore.py']

    tests = []
    # datetime info seems to be buried in GlobalConfig.results[0].run_id,
    # which makes ORM-level sorting problematic
    for gc in Session.query(GlobalConfig).all()[::-1]:
        gc.scripts = dict((uc.script, uc) for uc in gc.user_group_configs)
        if gc.results:
            for script, uc in gc.scripts.items():
                uc.results = filter(
                    lambda res: res.user_group_name == uc.user_group,
                    gc.results
                )
            test = {
                'datetime': gc.results[0].run_id,
                'run_time': gc.run_time,
                'results': gc.results,
            }
            for script in scripts:
                test[script.split('.')[0]] = gc.scripts.get(script)
            tests.append(test)

    context = get_hqadmin_base_context(request)
    context.update({
        "tests": tests,
        "hide_filters": True,
    })

    date_axis = Axis(label="Date", dateFormat="%m/%d/%Y")
    tests_axis = Axis(label="Number of Tests in 30s")
    chart = LineChart("HQ Load Test Performance", date_axis, tests_axis)
    submit_data = []
    ota_data = []
    total_data = []
    max_val = 0
    max_date = None
    min_date = None
    for test in tests:
        date = test['datetime']
        total = len(test['results'])
        max_val = total if total > max_val else max_val
        max_date = date if not max_date or date > max_date else max_date
        min_date = date if not min_date or date < min_date else min_date
        submit_data.append({'x': date, 'y': len(test['submit_form'].results)})
        ota_data.append({'x': date, 'y': len(test['ota_restore'].results)})
        total_data.append({'x': date, 'y': total})

    deployments = [row['key'][1] for row in HqDeploy.get_list(settings.SERVER_ENVIRONMENT, min_date, max_date)]
    deploy_data = [{'x': min_date, 'y': 0}]
    for date in deployments:
        deploy_data.extend([{'x': date, 'y': 0}, {'x': date, 'y': max_val}, {'x': date, 'y': 0}])
    deploy_data.append({'x': max_date, 'y': 0})

    chart.add_dataset("Deployments", deploy_data)
    chart.add_dataset("Form Submission Count", submit_data)
    chart.add_dataset("OTA Restore Count", ota_data)
    chart.add_dataset("Total Count", total_data)

    context['charts'] = [chart]

    template = "hqadmin/loadtest.html"
    return render(request, template, context)


def _lookup_id_in_couch(doc_id, db_name=None):
    if db_name:
        dbs = [couch_config.get_db(None if db_name == 'commcarehq' else db_name)]
    else:
        dbs = couch_config.all_dbs_by_slug.values()

    for db in dbs:
        try:
            doc = db.get(doc_id)
        except ResourceNotFound:
            pass
        else:
            return {
                "doc": json.dumps(doc, indent=4, sort_keys=True),
                "doc_id": doc_id,
                "doc_type": doc.get('doc_type', 'Unknown'),
                "dbname": db.dbname,
            }
    return {
        "doc": "NOT FOUND",
        "doc_id": doc_id,
    }


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
        "couch_info": _lookup_id_in_couch(doc_id),
    }
    return render(request, "hqadmin/doc_in_es.html", context)


@require_superuser
def raw_couch(request):
    doc_id = request.GET.get("id")
    db_name = request.GET.get("db_name", None)
    context = _lookup_id_in_couch(doc_id, db_name) if doc_id else {}
    other_dbs = sorted(filter(None, couch_config.all_dbs_by_slug.keys()))
    context['all_databases'] = ['commcarehq'] + other_dbs
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
                user_case = get_case_by_domain_hq_user_id(doc['domain'], doc['_id'], case_type)
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
        new_dict = SortedDict()
        key_list = sorted(indicators.keys())
        for key in key_list:
            new_dict[key] = indicators[key]
        return {
            'indicators': new_dict,
            'case': CommCareCase.get(case_id),
        }

    if user or user_case:
        custom_cache = None if enable_caching else cache.caches['dummy']
        cci = CallCenterIndicators(
            domain.name,
            domain.default_timezone,
            domain.call_center_config.case_type,
            user,
            custom_cache=custom_cache,
            override_date=query_date,
            override_cases=[user_case] if user_case else None
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


@require_superuser
def malt_as_csv(request):
    from django.core.exceptions import ValidationError

    if 'year_month' in request.GET:
        try:
            year, month = request.GET['year_month'].split('-')
            year, month = int(year), int(month)
            return _malt_csv_response(month, year)
        except (ValueError, ValidationError):
            messages.error(request, "Enter a valid year-month. e.g. 2015-09 (for December 2015)")
            return render(request, "hqadmin/malt_downloader.html")
    else:
        return render(request, "hqadmin/malt_downloader.html")


def _malt_csv_response(month, year):
    query_month = "{year}-{month}-01".format(year=year, month=month)
    queryset = MALTRow.objects.filter(month=query_month)
    return export_as_csv_action(exclude=['id'])(MALTRowAdmin, None, queryset)
