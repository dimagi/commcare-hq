from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import json
import socket
from collections import defaultdict, namedtuple

import requests
from django.conf import settings
from django.http import (
    HttpResponse,
)
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.views.decorators.http import require_POST
from requests.exceptions import HTTPError

from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor)
from corehq.apps.hqadmin.service_checks import run_checks
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.toggles import any_toggle_enabled, SUPPORT
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db, is_bigcouch
from dimagi.utils.web import json_response
from pillowtop.exceptions import PillowNotFoundError
from pillowtop.utils import get_all_pillows_json, get_pillow_json, get_pillow_config_by_name
from corehq.apps.hqadmin import service_checks, escheck
from corehq.apps.hqadmin.history import get_recent_changes, download_changes
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.hqadmin.utils import get_celery_stats
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView, get_hqadmin_base_context


class SystemInfoView(BaseAdminSectionView):
    page_title = ugettext_lazy("System Info")
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
        context['deploy_history'] = HqDeploy.get_latest(environment, limit=5)

        context['user_is_support'] = hasattr(self.request, 'user') and SUPPORT.enabled(self.request.user.username)

        context['redis'] = service_checks.check_redis()
        context['rabbitmq'] = service_checks.check_rabbitmq()
        context['celery_stats'] = get_celery_stats()
        context['heartbeat'] = service_checks.check_heartbeat()

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
    db = XFormInstance.get_db()
    if type == "_active_tasks":
        try:
            tasks = [x for x in db.server.active_tasks() if x['type'] == "indexer"]
        except HTTPError as e:
            if e.response.status_code == 403:
                return json_response({'error': "Unable to access CouchDB Tasks (unauthorized)."}, status_code=500)
            else:
                return json_response({'error': "Unable to access CouchDB Tasks."}, status_code=500)

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
                    task['progress_contribution'] = task['changes_done'] * 100 // total_changes

                design_docs.append(meta)
            return json_response(design_docs)
    elif type == "_stats":
        return json_response({})
    elif type == "_logs":
        pass
    elif type == 'pillowtop':
        pillow_meta = get_all_pillows_json()
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
        if type == "flower_poll":
            ret = []
            try:
                all_tasks = requests.get(
                    celery_monitoring + '/api/tasks',
                    params={'limit': task_limit},
                    timeout=3,
                ).json()
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
        return json_response(response)

    if pillow:
        try:
            if operation == 'refresh':
                return get_response()
        except Exception as e:
            return get_response(str(e))
    else:
        return get_response("No pillow found with name '{}'".format(pillow_name))


def get_rabbitmq_management_url():
    if settings.BROKER_URL.startswith('amqp'):
        amqp_parts = settings.BROKER_URL.replace('amqp://', '').split('/')
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
     'submodules/auditcare-src',
     ...]
    """
    import sh
    git = sh.git.bake(_tty_out=False)
    return [
        line.strip()[1:].split()[1]
        for line in git.submodule()
    ]


class RecentCouchChangesView(BaseAdminSectionView):
    urlname = 'view_recent_changes'
    template_name = 'hqadmin/couch_changes.html'
    page_title = ugettext_lazy("Recent Couch Changes")

    @use_nvd3_v3
    @use_datatables
    @use_jquery_ui
    @method_decorator(require_superuser_or_contractor)
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
                {'label': l, 'value': v} for l, v in sorted(list(data_dict.items()), key=lambda tup: tup[1], reverse=True)
            ][:20]

        return {
            'count': count,
            'recent_changes': changes,
            'domain_data': {'key': 'domains', 'values': _to_chart_data(domain_counts)},
            'doc_type_data': {'key': 'doc types', 'values': _to_chart_data(doc_type_counts)},
        }


@require_superuser_or_contractor
def download_recent_changes(request):
    count = int(request.GET.get('changes', 10000))
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="recent_changes.csv"'
    download_changes(get_db(), count, resp)
    return resp
