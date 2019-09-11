import io

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

import requests
import requests.exceptions
from couchdbkit import BadValueError, ResourceNotFound

from dimagi.utils.couch.database import get_db
from dimagi.utils.web import json_request, json_response

from corehq.apps.api.models import require_api_user
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.views import BasePageView
from corehq.util.view_utils import json_error

from .models import CommCareBuild, CommCareBuildConfig, SemanticVersionProperty
from .utils import extract_build_info_from_filename, get_all_versions


@csrf_exempt  # is used by an API
@json_error
@require_api_user
def post(request):
    artifacts       = request.FILES.get('artifacts')
    build_number    = request.POST.get('build_number')
    version         = request.POST.get('version')
    try:
        build_number = int(build_number)
    except Exception:
        return HttpResponseBadRequest("build_number has to be a base-10 integer")

    if not artifacts:
        CommCareBuild.create_without_artifacts(version, build_number)
    else:
        CommCareBuild.create_from_zip(artifacts, build_number=build_number, version=version)
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
    page_title = ugettext_lazy("Edit CommCare Builds")

    @method_decorator(require_superuser)
    @use_jquery_ui
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @property
    def page_context(self):
        doc = CommCareBuildConfig.fetch()
        return {
            'doc': doc,
            'all_versions': get_all_versions(
                [v['build']['version'] for v in doc['menu']]
            ),
            'j2me_enabled_versions': CommCareBuild.j2me_enabled_build_versions()
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


KNOWN_BUILD_SERVER_LOGINS = {
    'http://build.dimagi.com:250/': (
        lambda session:
        session.get('http://build.dimagi.com:250/guestLogin.html?guest=1')
    )
}


@require_POST
def import_build(request):
    """
    example POST params:
    source: 'http://build.dimagi.com:250/repository/downloadAll/bt97/14163:id/artifacts.zip'
    version: '2.13.0'
    build_number: 32703

    """
    source = request.POST.get('source')
    version = request.POST.get('version')
    build_number = request.POST.get('build_number')

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

    if build_number:
        # Strip and remove
        # U+200B ZERO WIDTH SPACE
        # https://manage.dimagi.com/default.asp?262198
        build_number = build_number.strip().replace('\u200b', '')
        try:
            build_number = int(build_number)
        except ValueError:
            return json_response({
                'reason': 'build_number must be an int'
            }, status_code=400)

    session = requests.session()

    # log in to the build server if we know how
    for key in KNOWN_BUILD_SERVER_LOGINS:
        if source.startswith(key):
            KNOWN_BUILD_SERVER_LOGINS[key](session)

    if source:
        r = session.get(source)

        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError:
            return json_response({
                'reason': 'Fetching artifacts.zip failed',
                'response': {
                    'status_code': r.status_code,
                    'content': r.content,
                    'headers': r.headers,
                }
            }, status_code=400)
        try:
            _, inferred_build_number = (
                extract_build_info_from_filename(r.headers['content-disposition'])
            )
        except (KeyError, ValueError):  # no header or header doesn't match
            inferred_build_number = None

        if inferred_build_number:
            build_number = inferred_build_number

        if not build_number:
            return json_response({
                'reason': "You didn't give us a build number "
                          "and we couldn't infer it"
            }, status_code=400)

        build = CommCareBuild.create_from_zip(
            io.BytesIO(r.content), version, build_number)

    else:
        build = CommCareBuild.create_without_artifacts(version, build_number)
    return json_response({
        'message': 'New CommCare build added',
        'info': {
            'version': version,
            'build_number': build_number,
            '_id': build.get_id,
        }
    })
