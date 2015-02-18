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
