import logging

from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _

from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context


@login_required
def ajax_job_poll(request, download_id, template="soil/partials/dl_status.html"):
    message = request.GET['message'] if 'message' in request.GET else None
    try:
        context = get_download_context(download_id, message=message)
    except TaskFailedError as e:
        context = {'error': list(e.errors) if e.errors else [_("An error occurred during the download.")]}
        return HttpResponseServerError(render(request, template, context))
    return render(request, template, context)


@login_required
def retrieve_download(request, download_id, template="soil/file_download.html", extra_context=None):
    """
    Retrieve a download that's waiting to be generated. If it is the get_file,
    then download it, else, let the ajax on the page poll.
    """
    context = RequestContext(request)
    if extra_context:
        context.update(extra_context)
    context['download_id'] = download_id

    if 'get_file' in request.GET:
        download = DownloadBase.get(download_id)
        if download is None:
            logging.error("Download file request for expired/nonexistent file requested")
            raise Http404
        return download.toHttpResponse()

    return render(request, template, context=context.flatten())
