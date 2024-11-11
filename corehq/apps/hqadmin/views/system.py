import socket
from collections import defaultdict, namedtuple

from couchdbkit import Server

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

import requests
from requests.exceptions import HTTPError

from dimagi.utils.couch.database import is_bigcouch
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import (
    get_all_pillows_json,
    get_pillow_config_by_name,
    get_pillow_json,
)

from corehq.apps.domain.decorators import (
    require_superuser,
    require_superuser_or_contractor,
)
from corehq.apps.domain.views.internal import get_project_limits_context
from corehq.apps.hqadmin import escheck, service_checks
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.service_checks import run_checks
from corehq.apps.hqadmin.utils import get_celery_stats
from corehq.apps.hqadmin.views.utils import (
    BaseAdminSectionView,
    get_hqadmin_base_context,
)
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui
from corehq.apps.receiverwrapper.rate_limiter import (
    global_submission_rate_limiter,
)
from corehq.toggles import SUPPORT


class SystemInfoView(BaseAdminSectionView):
    page_title = gettext_lazy("System Info")
    urlname = 'system_info'
    template_name = "hqadmin/system_info.html"

    @use_datatables
    @use_jquery_ui
    @method_decorator(require_superuser_or_contractor)
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
        context['deploy_history'] = HqDeploy.objects.filter(environment=environment)[:5]

        context['user_is_support'] = hasattr(self.request, 'user') and SUPPORT.enabled(self.request.user.username)

        context['redis'] = service_checks.check_redis()
        context['rabbitmq'] = service_checks.check_rabbitmq(settings.CELERY_BROKER_URL)
        context['celery_stats'] = get_celery_stats()

        context['cluster_health'] = escheck.check_es_cluster_health()

        return context


@require_superuser_or_contractor
def system_ajax(request):
    """
    Utility ajax functions for polling couch and celerymon
    """
    type = request.GET.get('api', None)
    task_limit = getattr(settings, 'CELERYMON_TASK_LIMIT', 12)
    celery_monitoring = getattr(settings, 'CELERY_FLOWER_URL', None)
    if type == "_active_tasks":
        server = Server(settings.COUCH_DATABASE)
        try:
            tasks = [x for x in server.active_tasks() if x['type'] == "indexer"]
        except HTTPError as e:
            if e.response.status_code == 403:
                return JsonResponse({'error': "Unable to access CouchDB Tasks (unauthorized)."}, status=500)
            else:
                return JsonResponse({'error': "Unable to access CouchDB Tasks."}, status=500)

        if not is_bigcouch():
            return JsonResponse(tasks, safe=False)
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
                    task['progress_contribution'] = task['changes_done'] * 100 // total_changes

                design_docs.append(meta)
            return JsonResponse(design_docs, safe=False)
    elif type == "_stats":
        return JsonResponse({})
    elif type == "_logs":
        pass
    elif type == 'pillowtop':
        pillow_meta = get_all_pillows_json()
        return JsonResponse(sorted(pillow_meta, key=lambda m: m['name'].lower()), safe=False)

    if celery_monitoring:
        if type == "flower_poll":
            ret = []
            try:
                all_tasks = requests.get(
                    celery_monitoring + '/api/tasks',
                    params={'limit': task_limit},
                    timeout=3,
                ).json()
            except Exception as ex:
                return JsonResponse({'error': "Error with getting from celery_flower: %s" % ex}, status=500)

            for task_id, traw in all_tasks.items():
                # it's an array of arrays - looping through [<id>, {task_info_dict}]
                if 'name' in traw and traw['name']:
                    traw['name'] = '.'.join(traw['name'].split('.')[-2:])
                else:
                    traw['name'] = None
                ret.append(traw)
            ret = sorted(ret, key=lambda x: x['succeeded'], reverse=True)
            return JsonResponse(ret, safe=False)
    return JsonResponse({})


@require_superuser_or_contractor
def check_services(request):

    def get_message(service_name, result):
        if result.exception:
            status = "EXCEPTION"
            msg = repr(result.exception)
        else:
            status = "SUCCESS" if result.success else "FAILURE"
            msg = result.msg
        return "{} (Took {:6.2f}s) {:15}: {}<br/>".format(status, result.duration, service_name, msg)

    statuses = run_checks(list(service_checks.CHECKS))
    results = [
        get_message(name, status) for name, status in statuses
    ]
    return HttpResponse("<pre>" + "".join(results) + "</pre>")


@require_POST
@require_superuser_or_contractor
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
        if pillow_config:
            response.update(get_pillow_json(pillow_config))
        return JsonResponse(response)

    if pillow:
        try:
            if operation == 'refresh':
                return get_response()
        except Exception as e:
            return get_response(str(e))
    else:
        return get_response("No pillow found with name '{}'".format(pillow_name))


def get_rabbitmq_management_url():
    if settings.CELERY_BROKER_URL.startswith('amqp'):
        amqp_parts = settings.CELERY_BROKER_URL.replace('amqp://', '').split('/')
        mq_management_url = amqp_parts[0].replace('5672', '15672')
        return "http://%s" % mq_management_url.split('@')[-1]
    else:
        return None


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

    # sh returning string from command git.log(...)
    branches = pipe.strip().split("\n")
    CommitBranchPair = namedtuple('CommitBranchPair', ['commit', 'branch'])
    return sorted(
        (CommitBranchPair(
            *line.strip()
            .replace("Merge remote-tracking branch 'origin/", '')
            .replace("Merge branch '", '')
            .replace("' into autostaging", '')
            .split(' ')[1:]
        ) for line in branches),
        key=lambda pair: pair.branch
    )


def _get_submodules():
    """
    returns something like
    ['submodules/commcare-translations', 'submodules/django-digest-src', ...]
    """
    import sh
    git = sh.git.bake(_tty_out=False)
    submodules = git.submodule().strip().split("\n")
    return [
        line.strip()[1:].split()[1]
        for line in submodules
    ]


@method_decorator(require_superuser, name='dispatch')
class GlobalThresholds(BaseAdminSectionView):
    urlname = 'global_thresholds'
    page_title = gettext_lazy("Global Usage Thresholds")
    template_name = 'hqadmin/global_thresholds.html'

    @property
    def page_context(self):
        return get_project_limits_context([
            ('Submission Rate Limits', global_submission_rate_limiter),
        ])
