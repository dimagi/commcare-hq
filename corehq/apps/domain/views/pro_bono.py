from __future__ import absolute_import, unicode_literals

from django.urls import reverse
from django.utils.translation import ugettext_lazy

from corehq.apps.domain.forms import ProBonoForm
from corehq.apps.domain.views.accounting import DomainAccountingSettings, DomainSubscriptionView
from corehq.apps.hqwebapp.views import BasePageView
from memoized import memoized


class ProBonoMixin(object):
    page_title = ugettext_lazy("Pro-Bono Application")
    is_submitted = False

    url_name = None

    @property
    def requesting_domain(self):
        raise NotImplementedError

    @property
    @memoized
    def pro_bono_form(self):
        if self.request.method == 'POST':
            return ProBonoForm(self.use_domain_field, self.request.POST)
        return ProBonoForm(self.use_domain_field)

    @property
    def page_context(self):
        return {
            'pro_bono_form': self.pro_bono_form,
            'is_submitted': self.is_submitted,
        }

    @property
    def page_url(self):
        return self.url_name

    def post(self, request, *args, **kwargs):
        if self.pro_bono_form.is_valid():
            self.pro_bono_form.process_submission(domain=self.requesting_domain)
            self.is_submitted = True
        return self.get(request, *args, **kwargs)


class ProBonoStaticView(ProBonoMixin, BasePageView):
    template_name = 'domain/pro_bono/static.html'
    urlname = 'pro_bono_static'
    use_domain_field = True

    @property
    def requesting_domain(self):
        return self.pro_bono_form.cleaned_data['domain']


class ProBonoView(ProBonoMixin, DomainAccountingSettings):
    template_name = 'domain/pro_bono/domain.html'
    urlname = 'pro_bono'
    use_domain_field = False

    @property
    def requesting_domain(self):
        return self.domain

    @property
    def parent_pages(self):
        return [
            {
                'title': DomainSubscriptionView.page_title,
                'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
            }
        ]

    @property
    def section_url(self):
        return self.page_url
