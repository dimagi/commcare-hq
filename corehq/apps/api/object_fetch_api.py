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
from corehq.apps.reports.views import can_view_attachments, safely_get_form, require_form_view_permission
from corehq.form_processor.exceptions import CaseNotFound, AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, get_cached_case_attachment, FormAccessors


class CaseAttachmentAPI(View):

    @method_decorator(api_auth)
    def get(self, request, domain, case_id=None, attachment_id=None):
        """
        https://github.com/dimagi/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """

        if self.request.couch_user.is_web_user() and not can_view_attachments(self.request):
            return HttpResponseForbidden()

        if not case_id or not attachment_id:
            raise Http404

        img = self.request.GET.get('img', None)
        size = self.request.GET.get('size', OBJECT_ORIGINAL)
        max_width = int(self.request.GET.get('max_image_width', 0))
        max_height = int(self.request.GET.get('max_image_height', 0))
        max_filesize = int(self.request.GET.get('max_size', 0))

        try:
            CaseAccessors(domain).get_case(case_id)
        except CaseNotFound:
            raise Http404

        if img is not None:
            if size == "debug_all":
                url_base = reverse("api_case_attachment", kwargs={
                    "domain": self.request.domain,
                    "case_id": case_id,
                    "attachment_id": attachment_id,
                })

                r = HttpResponse(content_type="text/html")
                r.write('<html><body>')
                r.write('<ul>')
                for fsize in IMAGE_SIZE_ORDERING:
                    meta, stream = fetch_case_image(
                        domain,
                        case_id,
                        attachment_id,
                        filesize_limit=max_filesize,
                        width_limit=max_width,
                        height_limit=max_height,
                        fixed_size=fsize
                    )

                    r.write('<li>')
                    r.write('Size: %s<br>' % fsize)
                    r.write("Limit: max_size: %s" % max_filesize)
                    if max_width > 0:
                        r.write(", max_width: %s" % max_width)
                    if max_height > 0:
                        r.write(", max_height: %s" % max_height)
                    r.write("<br>")
                    if meta is not None:
                        r.write('Resolution: %d x %d<br>' % (meta['width'], meta['height']))
                        r.write('Filesize: %d<br>' % meta['content_length'])

                        url_params = six.moves.urllib.parse.urlencode({
                            "img": '1',
                            "size": fsize,
                            "max_size": max_filesize,
                            "max_image_width": max_width,
                            "max_image_height": max_height
                        })
                        r.write('<img src="%(attach_url)s?%(params)s">' % {
                                "attach_url": url_base,
                                "params": url_params
                        })
                    else:
                        r.write('Not available')
                    r.write('</li>')
                r.write('</ul></body></html>')
                return r
            else:
                attachment_meta, attachment_stream = fetch_case_image(
                    domain,
                    case_id,
                    attachment_id,
                    filesize_limit=max_filesize,
                    width_limit=max_width,
                    height_limit=max_height,
                    fixed_size=size
                )
        else:
            cached_attachment = get_cached_case_attachment(domain, case_id, attachment_id)
            attachment_meta, attachment_stream = cached_attachment.get()

        if attachment_meta is not None:
            mime_type = attachment_meta['content_type']
        else:
            mime_type = "plain/text"

        return StreamingHttpResponse(streaming_content=FileWrapper(attachment_stream),
                                     content_type=mime_type)


@location_safe
class FormAttachmentAPI(View):

    @method_decorator(api_auth)
    @method_decorator(require_form_view_permission)
    def get(self, request, domain, form_id=None, attachment_id=None):
        if not form_id or not attachment_id:
            raise Http404

        # this raises a PermissionDenied error if necessary
        safely_get_form(request, domain, form_id)

        try:
            content = FormAccessors(domain).get_attachment_content(form_id, attachment_id)
        except AttachmentNotFound:
            raise Http404

        return StreamingHttpResponse(
            streaming_content=FileWrapper(content.content_stream),
            content_type=content.content_type
        )


def fetch_case_image(domain, case_id, attachment_id, filesize_limit=0, width_limit=0, height_limit=0, fixed_size=None):
    """
    Return (metadata, stream) information of best matching image attachment.

    :param attachment_id: the identifier of the attachment to fetch
    """
    if fixed_size is not None:
        size_key = fixed_size
    else:
        size_key = OBJECT_ORIGINAL

    constraint_dict = {}
    if filesize_limit:
        constraint_dict['content_length'] = filesize_limit

    if height_limit:
        constraint_dict['height'] = height_limit

    if width_limit:
        constraint_dict['width'] = width_limit
    do_constrain = bool(constraint_dict)

    cached_image = get_cached_case_attachment(domain, case_id, attachment_id, is_image=True)
    meta, stream = cached_image.get(size_key=size_key)

    if do_constrain:
        def meets_constraint(constraints, meta):
            for c, limit in constraints.items():
                if meta[c] > limit:
                    return False
            return True

        if not meets_constraint(constraint_dict, meta):
            # this meta is no good, find another one
            lesser_keys = IMAGE_SIZE_ORDERING[0:IMAGE_SIZE_ORDERING.index(size_key)]
            lesser_keys.reverse()
            is_met = False
            for lesser_size in lesser_keys:
                less_meta, less_stream = cached_image.get_size(lesser_size)
                if meets_constraint(constraint_dict, less_meta):
                    meta = less_meta
                    stream = less_stream
                    is_met = True
                    break
            if not is_met:
                meta = None
                stream = None

    return meta, stream
