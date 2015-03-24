import codecs
import os
import markdown
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin
from corehq.apps.public.forms import ContactDimagiForm


def public_default(request):
    return HttpResponseRedirect(reverse(HomePublicView.urlname))


class HomePublicView(JSONResponseMixin, TemplateView):
    urlname = 'public_home'
    template_name = 'public/home.html'

    def get_context_data(self, **kwargs):
        kwargs['contact_form'] = ContactDimagiForm()
        kwargs['is_home'] = True
        return super(HomePublicView, self).get_context_data(**kwargs)

    @allow_remote_invocation
    def send_email(self, in_data):
        # todo send and validate form
        return {
            'success': True,
        }


class ImpactPublicView(TemplateView):
    urlname = 'public_impact'
    template_name = 'public/impact.html'

    def get_context_data(self, **kwargs):
        pub_col1 = os.path.join(
            os.path.dirname(__file__), '_resources/publications_col1.md'
        )
        with codecs.open(pub_col1, mode="r", encoding="utf-8") as f:
            kwargs['pub_first_col'] = mark_safe(markdown.markdown(f.read()))

        pub_col2 = os.path.join(
            os.path.dirname(__file__), '_resources/publications_col2.md'
        )
        with codecs.open(pub_col2, mode="r", encoding="utf-8") as f:
            kwargs['pub_second_col'] = mark_safe(markdown.markdown(f.read()))

        kwargs['is_impact'] = True

        return super(ImpactPublicView, self).get_context_data(**kwargs)


class ServicesPublicView(TemplateView):
    urlname = 'public_services'
    template_name = 'public/services.html'


class PricingPublicView(TemplateView):
    urlname = 'public_pricing'
    template_name = 'public/pricing.html'

