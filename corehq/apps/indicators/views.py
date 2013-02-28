from django.shortcuts import render
from corehq.apps.crud.views import BaseAdminCRUDFormView
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.indicators.admin.crud import IndicatorCRUDFormRequestManager
from corehq.apps.indicators.dispatcher import require_edit_indicators


@require_edit_indicators
@login_and_domain_required
def default_admin(request, domain, template="reports/base_template.html", **kwargs):
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


class IndicatorAdminCRUDFormView(BaseAdminCRUDFormView):
    base_loc = "corehq.apps.indicators.admin.forms"
    form_request_manager = IndicatorCRUDFormRequestManager

