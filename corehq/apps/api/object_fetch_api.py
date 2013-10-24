from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from dimagi.utils.django.cached_object import IMAGE_SIZE_ORDERING, OBJECT_ORIGINAL
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_or_digest_ex


class CaseAttachmentAPI(View):
    @method_decorator(login_or_digest_ex(allow_cc_users=True))
    def get(self, *args, **kwargs):
        """
        https://bitbucket.org/commcare/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """

        max_filesize = int(self.request.GET.get('max_size', 0)) #todo

        img = self.request.GET.get('img', None)
        size = self.request.GET.get('size', OBJECT_ORIGINAL) #alternative to abs size
        max_width = int(self.request.GET.get('max_image_width', 0))
        max_height = int(self.request.GET.get('max_image_height', 0))

        case_id = kwargs.get('case_id', None)
        if not case_id or not CommCareCase.get_db().doc_exist(case_id):
            raise Http404

        attachment_key = kwargs.get('attachment_id', None)
        attachment_src = kwargs.get('attachment_src', None)

        if img is not None:
            if size == "debug_all":
                case_doc = CommCareCase.get(case_id)
                r = HttpResponse(content_type="text/html")
                r.write('<html><body>')
                r.write('<ul>')
                for fsize in IMAGE_SIZE_ORDERING:
                    meta, stream = CommCareCase.fetch_case_image(case_id, attachment_key, attachment_src, filesize_limit=max_filesize, width_limit=max_width, height_limit=max_height, fixed_size=fsize)

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
                                        "attachment_id": attachment_key,
                                        "attachment_src": attachment_src
                                    }),
                                    "domain": case_doc.domain, "case_id": case_id,
                                    "attachment_key": attachment_key,
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
                #image workflow
                attachment_meta, attachment_stream = CommCareCase.fetch_case_image(case_id, attachment_key, attachment_src, filesize_limit=max_filesize, width_limit=max_width, height_limit=max_height, fixed_size=size)
        else:
            #default stream
            attachment_meta, attachment_stream = CommCareCase.fetch_case_attachment(case_id, attachment_key, attachment_src)#, filesize_limit=max_size, width_limit=max_width, height_limit=max_height)

        if attachment_meta is not None:
            mime_type = attachment_meta['content_type']
        else:
            mime_type = "plain/text"
        response = StreamingHttpResponse(streaming_content=attachment_stream, mimetype=mime_type)
        return response

