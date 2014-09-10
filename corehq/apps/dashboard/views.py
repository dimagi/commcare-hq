from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop

from corehq import toggles
from corehq.apps.domain.views import DomainViewMixin, LoginAndDomainMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.style.decorators import preview_boostrap3


@toggles.DASHBOARD_PREVIEW.required_decorator()
def dashboard_default(request, domain):
    return HttpResponseRedirect(reverse(NewUserDashboardView.urlname,
                                        args=[domain]))


class BaseDashboardView(LoginAndDomainMixin, BasePageView, DomainViewMixin):

    @method_decorator(preview_boostrap3())
    @method_decorator(toggles.DASHBOARD_PREVIEW.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(BaseDashboardView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(BaseDashboardView, self).main_context
        context.update({
            'domain': self.domain,
        })
        return context

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])


class NewUserDashboardView(BaseDashboardView):
    urlname = 'dashboard_new_user'
    page_title = ugettext_noop("HQ Dashboard")
    template_name = 'dashboard/dashboard_new_user.html'


    @property
    def page_context(self):
        return {

        }

