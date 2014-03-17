from django.http import Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from tastypie.http import HttpBadRequest
from corehq.apps.crud.views import BaseCRUDFormView
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.indicators.admin.crud import IndicatorCRUDFormRequestManager
from corehq.apps.indicators.admin.forms import BulkCopyIndicatorsForm
from corehq.apps.indicators.dispatcher import require_edit_indicators
from corehq.apps.indicators.utils import get_indicator_domains
from dimagi.utils.modules import to_function


@require_edit_indicators
@login_and_domain_required
def default_admin(request, domain, template="reports/base_template.html", **kwargs):
    if request.domain not in get_indicator_domains():
        raise Http404
    from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
    context = dict(
        domain=domain,
        project=domain,
        report=dict(
            title="Select an Indicator Definition Type",
            show=True,
            slug=None,
            is_async=True,
            section_name=BaseIndicatorAdminInterface.section_name,
        )
    )
    return render(request, template, context)


class IndicatorAdminCRUDFormView(BaseCRUDFormView):
    base_loc = "corehq.apps.indicators.admin.forms"
    template_name = "indicators/forms/crud.add_indicator.html"
    form_request_manager = IndicatorCRUDFormRequestManager

    @method_decorator(require_edit_indicators)
    def dispatch(self, request, *args, **kwargs):
        return super(IndicatorAdminCRUDFormView, self).dispatch(request, *args, **kwargs)


class BulkCopyIndicatorsView(TemplateView):
    indicator_loc = "corehq.apps.indicators.models"
    template_name = "indicators/forms/copy_to_domain.html"

    @method_decorator(require_edit_indicators)
    def dispatch(self, request, domain, indicator_type=None, *args, **kwargs):
        self.domain = domain
        try:
            self.indicator_class = to_function("%s.%s" % (self.indicator_loc, indicator_type))
        except AttributeError:
            return HttpBadRequest("%s.%s does not exist" % (self.indicator_loc, indicator_type))

        status = {}

        if request.method == 'POST':
            form = BulkCopyIndicatorsForm(data=request.POST, domain=self.domain,
                                          couch_user=request.couch_user, indicator_class=self.indicator_class)
            if form.is_valid():
                status = form.copy_indicators()
        else:
            form = BulkCopyIndicatorsForm(domain=self.domain,
                                          couch_user=request.couch_user, indicator_class=self.indicator_class)

        return render(request, self.template_name, {
            "form": form,
            "status": status,
            "domain": self.domain,
            "indicator_type": self.indicator_class.__name__,
            "indicator_name": self.indicator_class.get_nice_name(),
        })
