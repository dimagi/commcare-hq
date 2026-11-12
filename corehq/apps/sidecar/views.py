from functools import cached_property

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.settings.views import BaseProjectDataView

from .models import SidecarApp


@method_decorator([
    use_bootstrap5,
    toggles.SIDECAR.required_decorator(),
    domain_admin_required,
], name='dispatch')
class SidecarAppView(BaseProjectDataView):
    urlname = 'sidecar_app'
    template_name = 'sidecar/sidecar_app.html'

    @cached_property
    def sidecar_app(self):
        return get_object_or_404(SidecarApp, domain=self.domain, slug=self.kwargs['slug'])

    @property
    def page_title(self):
        return self.sidecar_app.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.sidecar_app.slug])

    @property
    def page_context(self):
        return {'sidecar_app': self.sidecar_app}
