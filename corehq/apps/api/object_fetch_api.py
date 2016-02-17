from StringIO import StringIO
from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, StreamingHttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views.generic import View
from corehq.apps.reports.views import can_view_attachments
from couchforms.models import XFormInstance
from dimagi.utils.django.cached_object import IMAGE_SIZE_ORDERING, OBJECT_ORIGINAL, CachedImage
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_or_digest_or_basic_or_apikey


class CaseAttachmentAPI(View):
    @method_decorator(login_or_digest_or_basic_or_apikey())
    def get(self, request, domain, case_id=None, attachment_id=None):
        """
        https://github.com/dimagi/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """

        if self.request.couch_user.is_web_user() and not can_view_attachments(self.request):
            return HttpResponseForbidden()
        max_filesize = int(self.request.GET.get('max_size', 0)) #todo

        img = self.request.GET.get('img', None)
        size = self.request.GET.get('size', OBJECT_ORIGINAL) #alternative to abs size
        max_width = int(self.request.GET.get('max_image_width', 0))
        max_height = int(self.request.GET.get('max_image_height', 0))

        if not case_id or not attachment_id or CommCareCase.get_db().doc_exist(case_id):
            raise Http404

        if img is not None:
            if size == "debug_all":
                case_doc = CommCareCase.get(case_id)
                r = HttpResponse(content_type="text/html")
                r.write('<html><body>')
                r.write('<ul>')
                for fsize in IMAGE_SIZE_ORDERING:
                    meta, stream = CommCareCase.fetch_case_image(case_id, attachment_id, filesize_limit=max_filesize, width_limit=max_width, height_limit=max_height, fixed_size=fsize)

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
                        r.write('Filesize: %d<br>' % ( meta['content_length']))
                        r.write('<img src="%(attach_url)s?img&size=%(size_key)s&max_size=%(max_filesize)s&max_image_width=%(max_width)s&max_image_height=%(max_height)s">' %
                                {
                                    "attach_url": reverse("api_case_attachment", kwargs={
                                        "domain": self.request.domain,
                                        "case_id": case_id,
                                        "attachment_id": attachment_id,
                                    }),
                                    "domain": case_doc.domain, "case_id": case_id,
                                    "attachment_key": attachment_id,
                                    "size_key": fsize,
                                    "max_filesize": max_filesize,
                                    "max_width": max_width,
                                    "max_height": max_height
                                }
                        )
                    else:
                        r.write('Not available')
                    r.write('</li>')
                r.write('</ul></body></html>')
                return r
            else:
                # image workflow
                attachment_meta, attachment_stream = CommCareCase.fetch_case_image(case_id, attachment_id, filesize_limit=max_filesize, width_limit=max_width, height_limit=max_height, fixed_size=size)
        else:
            # default stream
            attachment_meta, attachment_stream = CommCareCase.fetch_case_attachment(case_id, attachment_id)

        if attachment_meta is not None:
            mime_type = attachment_meta['content_type']
        else:
            mime_type = "plain/text"
        response = StreamingHttpResponse(streaming_content=attachment_stream,
                content_type=mime_type)
        return response


class FormAttachmentAPI(View):
    @method_decorator(login_or_digest_or_basic_or_apikey())
    def get(self, request, domain, form_id=None, attachment_id=None):
        if not form_id or not attachment_id or not XFormInstance.get_db().doc_exist(form_id):
            raise Http404

        try:
            resp = XFormInstance.get_db().fetch_attachment(form_id, attachment_id, stream=True)
        except ResourceNotFound:
            raise Http404
        
        headers = resp.resp.headers
        content_type = headers.get('Content-Type', None)

        return StreamingHttpResponse(streaming_content=resp, content_type=content_type)


def fetch_case_image(case_id, attachment_key, filesize_limit=0, width_limit=0, height_limit=0, fixed_size=None):
    """
    Return (metadata, stream) information of best matching image attachment.
    attachment_key is the case property of the attachment
    attachment filename is the filename of the original submission - full extension and all.
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

    # if size key is None, then one of the limit criteria are set
    attachment_cache_key = "%(case_id)s_%(attachment)s" % {
        "case_id": case_id,
        "attachment": attachment_key,
    }

    cached_image = CachedImage(attachment_cache_key)
    meta, stream = cache_and_get_object(cached_image, case_id, attachment_key, size_key=size_key)

    # now that we got it cached, let's check for size constraints

    if do_constrain:
        #check this size first
        #see if the current size matches the criteria

        def meets_constraint(constraints, meta):
            for c, limit in constraints.items():
                if meta[c] > limit:
                    return False
            return True

        if meets_constraint(constraint_dict, meta):
            #yay, do nothing
            pass
        else:
            #this meta is no good, find another one
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


def cache_and_get_object(cobject, case_id, attachment_key, size_key=OBJECT_ORIGINAL):
    """
    Retrieve cached_object or image and cache sizes if necessary
    """
    if not cobject.is_cached():
        resp = CommCareCase.get_db().fetch_attachment(case_id, attachment_key, stream=True)
        stream = StringIO(resp.read())
        headers = resp.resp.headers
        cobject.cache_put(stream, headers)

    meta, stream = cobject.get(size_key=size_key)
    return meta, stream

