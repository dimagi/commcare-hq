from couchdbkit import ResourceNotFound
from django.http import HttpResponseBadRequest, HttpResponse, Http404
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.shortcuts import render
from django.utils.decorators import method_decorator
from dimagi.utils.web import json_request
from dimagi.utils.couch.database import get_db

from corehq.apps.api.models import require_api_user
from corehq.apps.domain.decorators import require_superuser

from .models import CommCareBuild, CommCareBuildConfig
from .utils import get_all_versions


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


class EditMenuView(TemplateView):
    template_name = "builds/edit_menu.html"
    doc_id = "config--commcare-builds"

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        self.doc = CommCareBuildConfig.fetch()
        return super(EditMenuView, self).dispatch(*args, **kwargs)

    def get_doc(self):
        db = get_db()
        return db.get(self.doc_id)

    def save_doc(self):
        db = get_db()
        return db.save_doc(self.doc)

    def get_context_data(self, **kwargs):
        context = {
            'doc': self.doc,
            'all_versions': get_all_versions(
                [v['build']['version'] for v in self.doc['menu']])
        }
        context.update(kwargs)
        return context

    def post(self, request, *args, **kwargs):
        request_json = json_request(request.POST)
        self.doc = request_json.get('doc')
        self.save_doc()
        return self.get(request, success=True, *args, **kwargs)
