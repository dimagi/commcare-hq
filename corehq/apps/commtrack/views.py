import json
import copy

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy
from corehq.apps.commtrack.const import SUPPLY_POINT_CASE_TYPE

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.domain.decorators import (
    domain_admin_required,
)
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import LocationType

from .forms import ConsumptionForm, StockLevelsForm, CommTrackSettingsForm
from .models import CommtrackActionConfig, StockRestoreConfig
from .tasks import recalculate_domain_consumption_task
from .util import all_sms_codes


@domain_admin_required
def default(request, domain):
    from corehq.apps.products.views import ProductListView
    if not (request.project and request.project.commtrack_enabled):
        raise Http404()
    return HttpResponseRedirect(reverse(ProductListView.urlname,
                                        args=[domain]))


class BaseCommTrackManageView(BaseDomainView):
    section_name = ugettext_lazy("Setup")

    @property
    def section_url(self):
        return reverse('default_commtrack_setup', args=[self.domain])

    @method_decorator(domain_admin_required)  # TODO: will probably want less restrictive permission?
    def dispatch(self, request, *args, **kwargs):
        return super(BaseCommTrackManageView, self).dispatch(request, *args, **kwargs)


class CommTrackSettingsView(BaseCommTrackManageView):
    urlname = 'commtrack_settings'
    page_title = ugettext_lazy("Advanced Settings")
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
        initial.update(dict(('consumption_' + k, v) for k, v in
            self.commtrack_settings.consumption_config.to_json().items()))
        initial.update(dict(('stock_' + k, v) for k, v in
            self.commtrack_settings.stock_levels_config.to_json().items()))

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
            self.domain_object.commtrack_settings.ota_restore_config = StockRestoreConfig(
                section_to_consumption_types={
                    'stock': 'consumption'
                },
                force_consumption_case_types=[
                    SUPPLY_POINT_CASE_TYPE
                ],
                use_dynamic_product_list=True,
            )
        else:
            self.domain_object.commtrack_settings.ota_restore_config = StockRestoreConfig()

    def post(self, request, *args, **kwargs):
        if self.commtrack_settings_form.is_valid():
            data = self.commtrack_settings_form.cleaned_data
            previous_config = copy.copy(self.commtrack_settings)
            self.commtrack_settings.use_auto_consumption = bool(data.get('use_auto_consumption'))
            self.commtrack_settings.sync_consumption_fixtures = bool(data.get('sync_consumption_fixtures'))
            self.commtrack_settings.individual_consumption_defaults = bool(data.get('individual_consumption_defaults'))

            self.set_ota_restore_config()

            fields = ('emergency_level', 'understock_threshold', 'overstock_threshold')
            for field in fields:
                if data.get('stock_' + field):
                    setattr(self.commtrack_settings.stock_levels_config, field,
                            data['stock_' + field])

            consumption_fields = ('min_transactions', 'min_window', 'optimal_window')
            for field in consumption_fields:
                if data.get('consumption_' + field):
                    setattr(self.commtrack_settings.consumption_config, field,
                            data['consumption_' + field])

            self.commtrack_settings.save()

            for loc_type in LocationType.objects.filter(domain=self.domain).all():
                # This will update stock levels based on commtrack config
                loc_type.save()

            if (previous_config.use_auto_consumption != self.commtrack_settings.use_auto_consumption
                or previous_config.consumption_config.to_json() != self.commtrack_settings.consumption_config.to_json()
            ):
                # kick off delayed consumption rebuild
                recalculate_domain_consumption_task.delay(self.domain)
                messages.success(request, _("Settings updated! Your updated consumption settings may take a "
                                            "few minutes to show up in reports and on phones."))
            else:
                messages.success(request, _("Settings updated!"))
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)


class DefaultConsumptionView(BaseCommTrackManageView):
    urlname = 'update_default_consumption'
    template_name = 'commtrack/manage/default_consumption.html'
    page_title = ugettext_lazy("Consumption")

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
    page_title = ugettext_lazy("SMS")
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
            'keyword': self.domain_object.commtrack_settings.multiaction_keyword,
            'actions': [self._get_action_info(a) for a in self.domain_object.commtrack_settings.actions],
            'requisition_config': {
                'enabled': self.domain_object.commtrack_settings.requisition_config.enabled,
                'actions': [self._get_action_info(a) for a in self.domain_object.commtrack_settings.requisition_config.actions],
            },
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
        for k, v in all_sms_codes(self.domain).iteritems():
            if v[0] == 'product':
                yield (k, (v[0], v[1].name))

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))

        self.domain_object.commtrack_settings.multiaction_keyword = payload['keyword']

        def mk_action(action):
            return CommtrackActionConfig(**{
                    'action': action['type'],
                    'subaction': action['caption'],
                    'keyword': action['keyword'],
                    'caption': action['caption'],
                })

        #TODO add server-side input validation here (currently validated on client)

        self.domain_object.commtrack_settings.actions = [mk_action(a) for a in payload['actions']]
        self.domain_object.commtrack_settings.requisition_config.enabled = payload['requisition_config']['enabled']
        self.domain_object.commtrack_settings.requisition_config.actions = [mk_action(a) for a in payload['requisition_config']['actions']]

        self.domain_object.commtrack_settings.save()

        return self.get(request, *args, **kwargs)


class StockLevelsView(BaseCommTrackManageView):
    urlname = 'stock_levels'
    page_title = ugettext_lazy("Stock Levels")
    template_name = 'commtrack/manage/stock_levels.html'

    def get_existing_stock_levels(self):
        loc_types = LocationType.objects.by_domain(self.domain)
        return [{
            'loc_type': loc_type.name,
            'emergency_level': loc_type.emergency_level,
            'understock_threshold': loc_type.understock_threshold,
            'overstock_threshold': loc_type.overstock_threshold,
        } for loc_type in loc_types]

    def save_stock_levels(self, levels):
        """
        Accepts a list of dicts of the form returned by
        get_existing_stock_levels and writes to the appropriate LocationType
        """
        levels = {level['loc_type']: level for level in levels}
        for loc_type in LocationType.objects.filter(domain=self.domain).all():
            if loc_type.name not in levels:
                continue

            stock_levels = levels[loc_type.name]
            changed = False
            for threshold in [
                'emergency_level',
                'understock_threshold',
                'overstock_threshold'
            ]:
                if getattr(loc_type, threshold) != stock_levels[threshold]:
                    setattr(loc_type, threshold, stock_levels[threshold])
                    changed = True
            if changed:
                loc_type.save()

    @property
    def page_context(self):
        return {
            'stock_levels_form': self.stock_levels_form
        }

    @property
    @memoized
    def stock_levels_form(self):
        if self.request.method == "POST":
            data = self.request.POST
        else:
            data = self.get_existing_stock_levels()
        return StockLevelsForm(data)

    def post(self, request, *args, **kwargs):
        if self.stock_levels_form.is_valid():
            self.save_stock_levels(self.stock_levels_form.cleaned_data)
            return HttpResponseRedirect(self.page_url)
        # TODO display error messages to the user...
        return self.get(request, *args, **kwargs)
