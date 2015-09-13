from django.http import HttpResponse, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from dimagi.utils.web import json_response

from .models import Deploy
from .exceptions import DeployAlreadyInProgress
from .utils import (
    get_uncommitted_submodules,
    commit_submodules,
    update_chief_code,
    build_staging,
    get_releases,
)

ENVIRONMENTS = ['staging', 'production', 'staging']


class ChiefDeploy(View):
    urlname = 'chief_deploy'

    def post(self, request, *args, **kwargs):
        """
        Initiates a new deploy by first committing submodules and pushing to master and then trigger the
        actual awesome_deploy
        """
        env = request.POST.get('env')

        if env != 'staging':
            submodules = request.POST.get('submodules', [])
            commit_submodules(env, submodules)

        deploy = Deploy.objects.create(env=env)
        #try:
        #    deploy = Deploy.create(env)
        #except DeployAlreadyInProgress:
        #    return HttpResponseBadRequest('There is already a deploy in progress')

        #deploy.deploy()

        return HttpResponse('Deploy has been triggered')

    def get(self, request, *args, **kwargs):
        """
        Returns a JSON representation of the current deploy status
        """
        deploy = Deploy.current_deploy()
        return json_response(deploy.as_json())


class ChiefDeployHook(View):
    urlname = 'chief_deploy_hook'

    def post(self, request, *args, **kwargs):
        machine = request.POST.get('machine')
        stage = request.POST.get('stage')
        env = request.POST.get('env')
        deploy = Deploy.current_deploy(env)

        deploy.add_stage(stage, machine)

        return HttpResponse('Successfully added stage')


class ChiefStatusPage(BasePageView):
    urlname = 'chief_status_page'
    page_title = 'HQ Chief'
    template_name = 'chief/status.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(ChiefStatusPage, self).dispatch(*args, **kwargs)

    def page_url(self):
        return reverse(self.urlname)

    def get_context_data(self, **kwargs):
        context = super(ChiefStatusPage, self).get_context_data(**kwargs)
        context.update({
            'hide_filters': True,
            # TODO make this dynamic so india can only deploy india
            'environments': ENVIRONMENTS,
            'deploys': Deploy.current_deploys()
        })
        return context


class ChiefReleases(View):
    urlname = 'chief_releases'

    def get(self, request, *args, **kwargs):
        releases = get_releases(ENVIRONMENTS)
        return json_response(releases)


class ChiefSubmodules(View):
    urlname = 'chief_submodules'

    def get(self, request, *args, **kwargs):
        env = request.GET.get('env')
        submodules = get_uncommitted_submodules(env)
        return json_response({'submodules': submodules})

    def post(self, request, *args, **kwargs):
        """
        Commits submodules and pushes them to master
        """


class ChiefPrepare(View):
    urlname = 'chief_prepare'

    def post(self, request, *args, **kwargs):
        env = request.POST.get('env')
        update_chief_code(env)
        if env == 'staging':
            try:
                build_staging(env)
            except Exception:
                json_response({'status': 'fail', 'reason': 'Failed to rebuild staging'}, status_code=500)
        return json_response({'status': 'ok'})
