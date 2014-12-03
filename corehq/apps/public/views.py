from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView


def public_default(request):
    return HttpResponseRedirect(reverse(HomePublicView.urlname))


class HomePublicView(TemplateView):
    urlname = 'public_home'
    template_name = 'public/home.html'
