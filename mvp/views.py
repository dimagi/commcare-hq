from corehq.apps.indicators.views import IndicatorAdminCRUDFormView


class MVPIndicatorAdminCRUDFormView(IndicatorAdminCRUDFormView):
    base_loc = "mvp.indicator_admin.forms"
