from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _

from corehq import toggles
from corehq.apps.campaign.forms import DashboardMapForm, DashboardReportForm, WidgetChoice
from corehq.apps.campaign.models import DashboardMap, Dashboard

from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.reports.views import BaseProjectReportSectionView
from corehq.util.htmx_action import HqHtmxActionMixin, HtmxResponseException, hq_hx_action


@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardView(BaseProjectReportSectionView):
    urlname = 'campaign_dashboard'
    page_title = _("Campaign Dashboard")
    template_name = 'campaign/dashboard.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'widget_choices': WidgetChoice.choices()
        })
        return context

@method_decorator(login_and_domain_required, name='dispatch')
@method_decorator(toggles.CAMPAIGN_DASHBOARD.required_decorator(), name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class DashboardWidgetView(HqHtmxActionMixin, BaseDomainView):
    urlname = "dashboard_widget"
    form_template_partial_name = 'campaign/partials/add_widget_form.html'

    def get(self, request, *args, **kwargs):
        widget = request.GET.get('widget')
        form_class = WidgetChoice.FORM_CLASS.get(widget)
        # TODO Add Validation Error
        form = form_class(domain=self.domain)
        context = {
            'add_widget_form': form,
            'widget': widget
        }
        return render(request, self.form_template_partial_name, context)

    @property
    def dashboard(self):
        dashboard, created = Dashboard.objects.get_or_create(domain=self.domain)
        return dashboard

    def post(self, request, *args, **kwargs):
        widget = request.PO.get('widget')
        form_class = WidgetChoice.FORM_CLASS.get(widget)
        form = form_class(self.request.POST, domain=self.domain)
        show_success = False
        if form.is_valid():
            form.save(commit=True)
            show_success = True
        else:
            context = {
                'add_widget_form': form,
                'show_success': show_success,
            }
            return render(request, self.form_template_partial_name, context)

        context = {
            'add_widget_form': form_class(domain=self.domain),
            'show_success': show_success,
        }
        return render(request, self.form_template_partial_name, context)
