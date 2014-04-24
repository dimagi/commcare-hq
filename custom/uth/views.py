from corehq.apps.domain.decorators import LoginAndDomainMixin
from braces.views import JSONResponseMixin
from django.views.generic import View


class ImageUploadView(JSONResponseMixin, View):
    def post(self, request, domain):
        self.domain = domain
        # TODO
