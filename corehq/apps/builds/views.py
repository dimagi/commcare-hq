from cStringIO import StringIO
from couchdbkit import ResourceNotFound, BadValueError
from django.core.urlresolvers import reverse
from django.http import HttpResponseBadRequest, HttpResponse, Http404
from django.utils.translation import ugettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView
from django.shortcuts import render
from django.utils.decorators import method_decorator
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.style.decorators import use_jquery_ui
from corehq.util.view_utils import json_error
from dimagi.utils.web import json_request, json_response
from dimagi.utils.couch.database import get_db

from corehq.apps.api.models import require_api_user
from corehq.apps.domain.decorators import require_superuser

from .models import CommCareBuild, CommCareBuildConfig, SemanticVersionProperty
from .utils import get_all_versions, extract_build_info_from_filename

import requests
import requests.exceptions


@csrf_exempt  # is used by an API
@json_error
@require_api_user
def post(request):
    artifacts       = request.FILES.get('artifacts')
    build_number    = request.POST.get('build_number')
    version         = request.POST.get('version')

    if not artifacts:
        return HttpResponseBadRequest("Must post a zip file called 'artifacts' with a username, password"
            "and the following meta-data: build_number (i.e. 2348), version (i.e. '1.2.3')")
    try:
        build_number = int(build_number)
    except Exception:
        print "%r" % build_number
        return HttpResponseBadRequest("build_number has to be a base-10 integer")

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
        # different local caches on different workers
        # but this at least makes it so your changes take effect immediately
        # while you're editing the config
        CommCareBuildConfig.clear_local_cache()
        self.doc = CommCareBuildConfig.fetch()
        return super(EditMenuView, self).dispatch(*args, **kwargs)

    def save_doc(self):
        db = get_db()
        return db.save_doc(self.doc)

    @property
    def page_context(self):
        return {
            'doc': self.doc,
            'all_versions': get_all_versions(
                [v['build']['version'] for v in self.doc['menu']])
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        request_json = json_request(request.POST)
        self.doc = request_json.get('doc')
        self.save_doc()
        return self.get(request, success=True, *args, **kwargs)


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
        SemanticVersionProperty().validate(version)
    except BadValueError as e:
        return json_response({
            'reason': 'Badly formatted version',
            'info': {
                'error_message': unicode(e),
                'error_type': unicode(type(e))
            }
        }, status_code=400)

    if build_number:
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
        StringIO(r.content), version, build_number)

    return json_response({
        'message': 'New CommCare build added',
        'info': {
            'version': version,
            'build_number': build_number,
            '_id': build.get_id,
        }
    })
