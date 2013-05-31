from django.core.servers.basehttp import FileWrapper
from django.http import HttpResponse, Http404
from django.utils.decorators import method_decorator, classonlymethod
from django.views.generic import View
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_and_domain_required
from django.core import cache


#following flickr's sizing convention with some additions




class CaseAttachmentAPI(View):
    @method_decorator(login_and_domain_required)
    def get(self, *args, **kwargs):
        """
        https://bitbucket.org/commcare/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """
        print "KWARGS"
        print kwargs
        max_size = self.request.GET.get('max_size', None)
        max_width = self.request.GET.get('max_image_width', None)
        max_height = self.request.GET.get('max_image_height', None)
        size = self.request.GET('size', None) #alternative to abs size

        if size:
            size_key = size
        else:
            if max_size:
                pass
            else:
                pass

        domain = self.request.domain
        print args
        case_id = kwargs.get('case_id', None)
        case_exists = CommCareCase.get_db().doc_exist(case_id)
        if not case_exists:
            raise Http404


        rcache = cache.get_cache('redis')

        attachment_data_key = "%(case_id)_%(attachment)s_%(size_key)s" % {
            "case_id": case_id,
            "attachment": attachment_key,
            "size_key": size_key
        }

        case_doc = CommCareCase.get(case_id)
        attachment_key = kwargs.get('attachment_id', None)
        attach_stream = CommCareCase.get_db().fetch_attachment(case_id, attachment_key, stream=True)
        wrapper = FileWrapper(attach_stream)
        attachment_meta = case_doc.case_attachments.get(attachment_key, {})
        mime_type = attachment_meta.server_mime

        response = HttpResponse(wrapper, mimetype=mime_type)
        return response

    @method_decorator(login_and_domain_required)
    def head(self, *args, **kwargs):
        pass

