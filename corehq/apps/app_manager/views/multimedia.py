from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import Http404, HttpResponse
from django.shortcuts import render
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_deploy_apps, \
    require_can_edit_apps
from corehq.apps.app_manager.xform import XForm, validate_xform
from corehq.util.view_utils import set_file_download


@require_can_edit_apps
def multimedia_list_download(request, domain, app_id):
    app = get_app(domain, app_id)
    include_audio = request.GET.get("audio", True)
    include_images = request.GET.get("images", True)
    strip_jr = request.GET.get("strip_jr", True)
    filelist = []
    for m in app.get_modules():
        for f in m.get_forms():
            validate_xform(domain, f.source)
            parsed = XForm(f.source)
            if include_images:
                filelist.extend(parsed.image_references)
            if include_audio:
                filelist.extend(parsed.audio_references)

    if strip_jr:
        filelist = [s.replace("jr://file/", "") for s in filelist if s]
    response = HttpResponse()
    set_file_download(response, 'list.txt')
    response.write("\n".join(sorted(set(filelist))))
    return response


@require_deploy_apps
def multimedia_ajax(request, domain, app_id):
    app = get_app(domain, app_id)
    if app.get_doc_type() == 'Application':
        multimedia_state = app.check_media_state()
        context = {
            'multimedia_state': multimedia_state,
            'domain': domain,
            'app': app,
        }
        return render(request, "app_manager/partials/multimedia_ajax.html", context)
    else:
        raise Http404()
