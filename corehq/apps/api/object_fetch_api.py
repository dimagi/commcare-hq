from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse, Http404
from django.utils.decorators import method_decorator
from django.views.generic import View
from dimagi.utils.django.cached_object import IMAGE_SIZE_ORDERING
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required


class CachedObjectAPI(View):
    @method_decorator(login_and_domain_required)
    def get(self, *args, **kwargs):
        """
        Return a cached object based upon the key in the URL
        """
        pass


class CaseAttachmentAPI(View):
    @method_decorator(login_and_domain_required)
    def get(self, *args, **kwargs):
        """
        https://bitbucket.org/commcare/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """

        max_size = self.request.GET.get('max_size', None)

        img = self.request.GET.get('img', None)
        size = self.request.GET.get('size', None) #alternative to abs size
        max_width = self.request.GET.get('max_image_width', None)
        max_height = self.request.GET.get('max_image_height', None)

        if size:
            size_key = size
        else:
            size_key = None

        domain = self.request.domain
        case_id = kwargs.get('case_id', None)
        case_exists = CommCareCase.get_db().doc_exist(case_id)
        if not case_exists:
            raise Http404

        attachment_key = kwargs.get('attachment_id', None)

        if img is not None:
            if size == "debug_all":
                case_doc = CommCareCase.get(case_id)
                r = HttpResponse(content_type="text/html")
                r.write('<html><body>')
                r.write('<ul>')
                for fsize in IMAGE_SIZE_ORDERING:
                    meta, stream = CommCareCase.fetch_case_image(case_id, attachment_key, filesize_limit=size, width_limit=max_width, height_limit=max_height, fixed_size=fsize)

                    r.write('<li>')
                    r.write('Size: %s<br>' % fsize)
                    r.write('Resolution: %d x %d<br>' % (meta['width'], meta['height']))
                    r.write('Filesize: %d<br>' % ( meta['content_length']))
                    r.write('<img src="/a/%s/api/case/attachment/%s/%s?img&size=%s">' % (case_doc.domain, case_id, attachment_key, fsize))
                    r.write('</li>')
                r.write('</ul></body></html>')
                return r
            else:
                #image workflow

                attachment_meta, attachment_stream = CommCareCase.fetch_case_image(case_id, attachment_key, filesize_limit=size, width_limit=max_width, height_limit=max_height, fixed_size=size)
        else:
            #default stream
            attachment_meta, attachment_stream = CommCareCase.fetch_case_attachment(case_id, attachment_key)#, filesize_limit=max_size, width_limit=max_width, height_limit=max_height)

        wrapper = FileWrapper(attachment_stream)
        mime_type = attachment_meta['content_type']
        response = HttpResponse(wrapper, mimetype=mime_type)
        return response

    @method_decorator(login_and_domain_required)
    def head(self, *args, **kwargs):
        pass

