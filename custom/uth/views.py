from corehq.apps.domain.views import BaseDomainView
from django.core.urlresolvers import reverse


class ImageUploadView(BaseDomainView):
    section_name = 'UTH Uploader'
    urlname = 'upload_images'
    template_name = 'uth/upload_images.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {

        }

    @property
    def section_url(self):
        return ''
        #return reverse('data_interfaces_default', args=[self.domain])
