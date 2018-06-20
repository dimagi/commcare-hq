from __future__ import absolute_import
from __future__ import unicode_literals
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from wsgiref.util import FileWrapper

from django.urls import reverse
from django.http import HttpResponse, Http404, StreamingHttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views.generic import View

from corehq.apps.locations.permissions import location_safe
from dimagi.utils.django.cached_object import IMAGE_SIZE_ORDERING, OBJECT_ORIGINAL

from corehq.apps.domain.decorators import api_auth
from corehq.apps.reports.views import _get_location_safe_form, require_form_view_permission
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors


@location_safe
class FormAttachmentAPI(View):

    @method_decorator(api_auth)
    @method_decorator(require_form_view_permission)
    def get(self, request, domain, form_id=None, attachment_id=None):
        if not form_id or not attachment_id:
            raise Http404

        # this raises a PermissionDenied error if necessary
        _get_location_safe_form(domain, request.couch_user, form_id)

        try:
            content = FormAccessors(domain).get_attachment_content(form_id, attachment_id)
        except AttachmentNotFound:
            raise Http404
        
        return StreamingHttpResponse(
            streaming_content=FileWrapper(content.content_stream),
            content_type=content.content_type
        )
