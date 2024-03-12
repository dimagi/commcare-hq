from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from couchdbkit import BadValueError, ResourceNotFound

from dimagi.utils.web import json_request, json_response

from corehq.apps.api.models import require_api_user
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.util.view_utils import json_error

from .models import CommCareBuild, CommCareBuildConfig, SemanticVersionProperty
from .utils import get_all_versions


@csrf_exempt  # is used by an API
@json_error
@require_api_user
def post(request):
    build_number = request.POST.get('build_number')
    version = request.POST.get('version')
    try:
        build_number = int(build_number)
    except ValueError:
        return HttpResponseBadRequest("build_number has to be a base-10 integer")

    CommCareBuild.create_without_artifacts(version, build_number)
    return HttpResponse()


@require_GET
def get(request, version, build_number, path):
    build = CommCareBuild.get_build(version, build_number)
    try:
        file = build.fetch_file(path)
    except ResourceNotFound:
        raise Http404()

    response = HttpResponse(file)
    response['Content-Disposition'] = 'attachment; filename="%s"' % path.split("/")[-1]
    return response


@require_GET
@require_superuser
def get_all(request):
    builds = sorted(CommCareBuild.all_builds(), key=lambda build: build.time)
    return render(request, 'builds/all.html', {'builds': builds})


class EditMenuView(BasePageView):
    template_name = "builds/edit_menu.html"
    urlname = 'edit_menu'
    doc_id = "config--commcare-builds"
    page_title = gettext_lazy("Edit CommCare Builds")

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @property
    def page_context(self):
        doc = CommCareBuildConfig.fetch()
        return {
            'doc': doc,
            'all_versions': get_all_versions(
                [v['build']['version'] for v in doc['menu']]
            )
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        request_json = json_request(request.POST)
        doc = request_json.get('doc')
        CommCareBuildConfig.get_db().save_doc(doc)
        CommCareBuildConfig.clear_local_cache()
        messages.success(request, "Your changes have been saved")
        return HttpResponseRedirect(self.page_url)


@require_POST
def import_build(request):
    """
    example POST params:
    version: '2.13.0'

    """
    version = request.POST.get('version')

    try:
        SemanticVersionProperty(required=True).validate(version)
    except BadValueError as e:
        return json_response({
            'reason': 'Badly formatted version',
            'info': {
                'error_message': str(e),
                'error_type': str(type(e))
            }
        }, status_code=400)

    build = CommCareBuild.create_without_artifacts(version, None)

    return json_response({
        'message': 'New CommCare build added',
        'info': {
            'version': version,
            '_id': build.get_id,
        }
    })
