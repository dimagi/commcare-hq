from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import render
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_deploy_apps, \
    require_can_edit_apps
from corehq.apps.app_manager.xform import XForm
from corehq.util.view_utils import set_file_download
from dimagi.utils.logging import notify_exception
from dimagi.utils.subprocess_timeout import ProcessTimedOut


@require_can_edit_apps
def multimedia_list_download(request, domain, app_id):
    app = get_app(domain, app_id)
    include_audio = request.GET.get("audio", True)
    include_images = request.GET.get("images", True)
    strip_jr = request.GET.get("strip_jr", True)
    filelist = []
    for m in app.get_modules():
        for f in m.get_forms():
            parsed = XForm(f.source)
            parsed.validate(version=app.application_version)
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
def multimedia_ajax(request, domain, app_id, template='app_manager/partials/multimedia_ajax.html',
                    extra_context=None):
    app = get_app(domain, app_id)
    if app.get_doc_type() == 'Application':
        try:
            multimedia_state = app.check_media_state()
        except ProcessTimedOut:
            notify_exception(request)
            messages.warning(request, (
                "We were unable to check if your forms had errors. "
                "Refresh the page and we will try again."
            ))
            multimedia_state = {
                'has_media': False,
                'has_form_errors': True,
                'has_missing_refs': False,
            }
        context = {
            'multimedia_state': multimedia_state,
            'domain': domain,
            'app': app,
            'multimedia_totals': app.get_reference_totals(),
        }
        if extra_context:
            context.update(extra_context)
        return render(request, template, context)
    else:
        raise Http404()


@require_deploy_apps
def multimedia_ajax_download(request, domain, app_id):
    template = 'hqmedia/partials/multimedia_zip_notice.html'
    return multimedia_ajax(request, domain, app_id, template, {'include_modal': True})
