from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import json
import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponse, HttpResponseServerError
from django.shortcuts import render_to_response, render
from django.template.context import RequestContext
from django.utils.translation import ugettext_lazy as _

from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.heartbeat import get_file_heartbeat, get_cache_heartbeat, last_heartbeat
from soil.tasks import demo_sleep
from soil.util import get_download_context
import six

from corehq.util.python_compatibility import soft_assert_type_text


def _parse_date(string):
    if isinstance(string, six.string_types):
        soft_assert_type_text(string)
        return datetime.strptime(string, "%Y-%m-%d").date()
    else:
        return string


@login_required
def demo(request):
    download_id = uuid.uuid4().hex
    howlong = int(request.GET.get('secs', 5))
    demo_sleep.delay(download_id, howlong)
    return HttpResponseRedirect(reverse('retrieve_download', kwargs={'download_id': download_id}))


@login_required
def heartbeat_status(request):
    return HttpResponse(json.dumps({"last_timestamp": str(last_heartbeat()),
                                    "last_from_file": get_file_heartbeat(),
                                    "last_from_cache": get_cache_heartbeat()}))


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

    return render_to_response(template, context=context.flatten())
