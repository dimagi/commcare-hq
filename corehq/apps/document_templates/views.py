from corehq.apps.document_templates.models import Template
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.sms.views import BaseMessagingSectionView


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.DOCUMENT_TEMPLATES.required_decorator(), name='dispatch')
class DocumentTemplatesView(BaseMessagingSectionView):
    urlname = 'document_templates'
    page_title = gettext_lazy('Document Templates')
    template_name = 'document_templates/template_list.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def page_context(self):
        return {
            'templates': Template.objects.filter(
                domain=self.domain,
            )
            .order_by('name')
        }
