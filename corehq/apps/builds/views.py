from django.http import HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_GET
from corehq.apps.api.models import require_api_user
from corehq.apps.builds.models import CommCareBuild

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
        return HttpResponseBadRequest("build_number has to be a base-10 integer")


    CommCareBuild.create_from_zip(artifacts, build_number=build_number, version=version)
    return HttpResponse()

@require_GET
def get(request, version, build_number, path):
    build = CommCareBuild.get_build(version, build_number)
    file = build.fetch_file(path)

    response = HttpResponse(file)
    response['Content-Disposition'] = "attachment; filename=%s" % path.split("/")[-1]
    return response