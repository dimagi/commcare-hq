from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.translation import (
    ugettext_lazy,
)
from django.utils.functional import cached_property
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.shortcuts import redirect

from corehq import toggles
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.permissions import location_safe
from corehq.apps.domain.decorators import login_and_domain_required
from custom.icds.forms import (
    CCZHostingLinkForm,
)
from custom.icds.models import CCZHostingLink


@location_safe
@method_decorator([toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.required_decorator()], name='dispatch')
class ManageCCZHostingLink(BaseDomainView):
    urlname = "manage_ccz_hosting_links"
    page_title = ugettext_lazy("Manage CCZ Hosting Links")
    template_name = 'icds/manage_ccz_hosting_links.html'
    section_name = ugettext_lazy("CCZ Hosting Links")

    @cached_property
    def section_url(self):
        return reverse(ManageCCZHostingLink.urlname, args=[self.domain])

    @cached_property
    def form(self):
        return CCZHostingLinkForm(
            data=self.request.POST if self.request.method == "POST" else None
        )

    def get_context_data(self, **kwargs):
        links = [l.to_json() for l in CCZHostingLink.objects.filter(domain=self.domain)]
        return {
            'form': self.form,
            'links': links,
            'domain': self.domain,
        }

    @method_decorator(login_and_domain_required)
    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.form.save()
            return redirect(self.urlname, domain=self.domain)
        return self.get(request, *args, **kwargs)


class EditCCZHostingLink(ManageCCZHostingLink):
    urlname = "edit_ccz_hosting_link"

    @cached_property
    def form(self):
        link = CCZHostingLink.objects.get(id=self.kwargs['link_id'])
        if self.request.POST:
            return CCZHostingLinkForm(instance=link, data=self.request.POST)
        return CCZHostingLinkForm(instance=link)

    def get_context_data(self, **kwargs):
        return {
            'form': self.form,
            'domain': self.domain,
        }
