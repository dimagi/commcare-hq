from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.views.generic import View, TemplateView
from corehq.apps.analytics.tasks import track_clicked_deploy_on_hubspot
from corehq.apps.analytics.utils import get_meta
from corehq.apps.analytics.forms import NewABForm
from corehq.apps.analytics.models import HubspotAB

from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.style.decorators import use_bootstrap3
from dimagi.utils.decorators.memoized import memoized


class HubspotClickDeployView(View):
    urlname = 'hubspot_click_deploy'

    def post(self, request, *args, **kwargs):
        meta = get_meta(request)
        track_clicked_deploy_on_hubspot.delay(request.couch_user, request.COOKIES, meta)
        return HttpResponse()

class ABTestSetupView(BasePageView):
    urlname = 'ab_test_setup'
    template_name = 'analytics/ab_test_setup.html'
    page_title = 'AB Test Setup'
    page_name = 'Set Up a New A/B Test'

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(ABTestSetupView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'form': self.ab_form,
            'success': self.success if hasattr(self, 'success') else False
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    @memoized
    def ab_form(self):
        if self.request.method == 'POST':
            return NewABForm(self.request.POST)
        else:
            return NewABForm()

    def post(self, request, *args, **kwargs):
        if self.ab_form.is_valid():
            self.ab_form.create_new_ab_test()
            self.success = self.ab_form.cleaned_data['slug']
        return self.get(request, *args, **kwargs)

class ABTestListView(BasePageView):
    urlname = 'ab_test_list'
    template_name = 'analytics/ab_test.html'
    page_title = 'AB Tests'
    page_name = 'AB Tests'

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(ABTestListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'tests': self.all_tests
        }

    @property
    def all_tests(self):
        return HubspotAB.objects.all()