from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from corehq.apps.domain.decorators import login_and_domain_required


class CaseAttachmentAPI(View):
    @method_decorator(login_and_domain_required)
    def get(self, *args, **kwargs):
        """
        https://bitbucket.org/commcare/commcare/wiki/CaseAttachmentAPI
        max_size	The largest size (in bytes) for the attachment
        max_image_width	The largest width in pixels for an an image attachment
        max_image_height	The largest width in pixels for an an image attachment
        """
        max_size = self.request.GET.get('max_size', 0)
        max_width = self.request.GET.get('max_image_width', 0)
        max_height = self.request.GET.get('max_image_height', 0)
        
        response = HttpResponse()
        return response
