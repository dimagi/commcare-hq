import decimal
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.utils import DataError
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq.apps.commtrack.const import SUPPLY_POINT_CASE_TYPE
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5, use_jquery_ui
from corehq.apps.locations.models import LocationType

from .forms import CommTrackSettingsForm, ConsumptionForm
from .models import ActionConfig, StockRestoreConfig
from .util import all_sms_codes


@domain_admin_required
def default(request, domain):
    if not (request.project and request.project.commtrack_enabled):
        raise Http404()
    return HttpResponseRedirect(default_commtrack_url(domain))


def default_commtrack_url(domain):
    from corehq.apps.products.views import ProductListView
    return reverse(ProductListView.urlname, args=[domain])


class BaseCommTrackManageView(BaseDomainView):
    section_name = gettext_noop("Setup")

    @property
    def section_url(self):
        return reverse('default_commtrack_setup', args=[self.domain])

    def get(self, *args, **kwargs):
        if self.domain_object.commtrack_settings is None:
            raise Http404()
        return super(BaseCommTrackManageView, self).get(*args, **kwargs)

    @method_decorator(domain_admin_required)  # TODO: will probably want less restrictive permission?
    def dispatch(self, request, *args, **kwargs):
        return super(BaseCommTrackManageView, self).dispatch(request, *args, **kwargs)


class CommTrackSettingsView(BaseCommTrackManageView):
    urlname = 'commtrack_settings'
    page_title = gettext_noop("Advanced Settings")
    template_name = 'domain/admin/commtrack_settings.html'

    @property
    @memoized
    def commtrack_settings(self):
        return self.domain_object.commtrack_settings

    @property
    def page_context(self):
        return {
            'form': self.commtrack_settings_form
        }

    @property
    @memoized
    def commtrack_settings_form(self):
        initial = self.commtrack_settings.to_json()
        if hasattr(self.commtrack_settings, 'consumptionconfig'):
            initial.update(dict(('consumption_' + k, v) for k, v in
                self.commtrack_settings.consumptionconfig.to_json().items()))
        if hasattr(self.commtrack_settings, 'stocklevelsconfig'):
            initial.update(dict(('stock_' + k, v) for k, v in
                self.commtrack_settings.stocklevelsconfig.to_json().items()))

        if self.request.method == 'POST':
            return CommTrackSettingsForm(self.request.POST, initial=initial, domain=self.domain)
        return CommTrackSettingsForm(initial=initial, domain=self.domain)

    def set_ota_restore_config(self):
        """
        If the checkbox for syncing consumption fixtures is
        checked, then we build the restore config with appropriate
        special properties, otherwise just clear the object.

        If there becomes a way to tweak these on the UI, this should
        be done differently.
        """

        if self.commtrack_settings.sync_consumption_fixtures:
            self.domain_object.commtrack_settings.stockrestoreconfig = StockRestoreConfig(
                section_to_consumption_types={
                    'stock': 'consumption'
                },
                force_consumption_case_types=[
                    SUPPLY_POINT_CASE_TYPE
                ],
                use_dynamic_product_list=True,
            )
        else:
            self.domain_object.commtrack_settings.stockrestoreconfig = StockRestoreConfig()

    def post(self, request, *args, **kwargs):
        if self.commtrack_settings_form.is_valid():
            data = self.commtrack_settings_form.cleaned_data
            for attr in ('use_auto_consumption', 'sync_consumption_fixtures', 'individual_consumption_defaults'):
                setattr(self.commtrack_settings, attr, bool(data.get(attr)))

            self.set_ota_restore_config()

            fields = ('emergency_level', 'understock_threshold', 'overstock_threshold')
            for field in fields:
                if data.get('stock_' + field):
                    setattr(self.commtrack_settings.stocklevelsconfig, field,
                            data['stock_' + field])

            consumption_fields = ('min_transactions', 'min_window', 'optimal_window')
            for field in consumption_fields:
                if data.get('consumption_' + field):
                    setattr(self.commtrack_settings.consumptionconfig, field,
                            data['consumption_' + field])

            try:
                self.commtrack_settings.save()
                for attr in ('consumptionconfig', 'stockrestoreconfig', 'stocklevelsconfig'):
                    submodel = getattr(self.commtrack_settings, attr)
                    submodel.commtrack_settings = self.commtrack_settings
                    submodel.save()
            except (decimal.InvalidOperation, DataError):      # capture only decimal errors and integer overflows
                try:
                    # Get human-readable messages
                    self.commtrack_settings.stocklevelsconfig.full_clean()
                    self.commtrack_settings.consumptionconfig.full_clean()
                except ValidationError as e:
                    for key, msgs in dict(e).items():
                        for msg in msgs:
                            messages.error(request, _("Could not save {}: {}").format(key, msg))

            for loc_type in LocationType.objects.filter(domain=self.domain).all():
                # This will update stock levels based on commtrack config
                loc_type.save()

            messages.success(request, _("Settings updated!"))
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)


@method_decorator(use_bootstrap5, name='dispatch')
class DefaultConsumptionView(BaseCommTrackManageView):
    urlname = 'update_default_consumption'
    template_name = 'commtrack/manage/default_consumption.html'
    page_title = gettext_noop("Consumption")

    @property
    @memoized
    def consumption_form(self):
        if self.request.method == 'POST':
            return ConsumptionForm(self.domain, self.request.POST)
        return ConsumptionForm(self.domain)

    @property
    def page_context(self):
        return {
            'form': self.consumption_form,
        }

    def post(self, request, *args, **kwargs):
        if self.consumption_form.is_valid():
            self.consumption_form.save()
            messages.success(request, _("Default consumption values updated"))
            return HttpResponseRedirect(
                reverse(DefaultConsumptionView.urlname, args=[self.domain])
            )
        return self.get(request, *args, **kwargs)


class SMSSettingsView(BaseCommTrackManageView):
    urlname = 'commtrack_sms_settings'
    page_title = gettext_noop("SMS")
    template_name = 'domain/admin/sms_settings.html'

    @property
    def page_context(self):
        return {
            'other_sms_codes': dict(self.get_other_sms_codes()),
            'settings': self.settings_context,
        }

    @property
    def settings_context(self):
        return {
            'actions': [self._get_action_info(a) for a in self.domain_object.commtrack_settings.all_actions],
        }

    # FIXME
    def _get_action_info(self, action):
        return {
            'type': action.action,
            'keyword': action.keyword,
            'name': action.subaction,
            'caption': action.caption,
        }

    def get_other_sms_codes(self):
        for k, v in all_sms_codes(self.domain).items():
            if v[0] == 'product':
                yield (k, (v[0], v[1].name))

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))

        def make_action(action):
            return ActionConfig(**{
                'action': action['type'],
                'subaction': action['caption'],
                'keyword': action['keyword'],
                'caption': action['caption'],
            })

        # TODO add server-side input validation here (currently validated on client)

        self.domain_object.commtrack_settings.set_actions([make_action(a) for a in payload['actions']])
        self.domain_object.commtrack_settings.save()

        return self.get(request, *args, **kwargs)

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(SMSSettingsView, self).dispatch(request, *args, **kwargs)
