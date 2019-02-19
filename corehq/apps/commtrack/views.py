from __future__ import absolute_import
from __future__ import unicode_literals
import json
import copy

from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.const import SUPPLY_POINT_CASE_TYPE
from corehq.apps.commtrack.processing import plan_rebuild_stock_state, \
    rebuild_stock_state
from corehq import toggles
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.exceptions import XFormNotFound
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.util.timezones.conversions import ServerTime

from memoized import memoized

from corehq.apps.domain.decorators import (
    domain_admin_required,
)
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.locations.models import LocationType, SQLLocation

from .forms import ConsumptionForm, StockLevelsForm, CommTrackSettingsForm
from .models import CommtrackActionConfig, StockRestoreConfig
from .tasks import recalculate_domain_consumption_task
from .util import all_sms_codes
import six


@domain_admin_required
def default(request, domain):
    if not (request.project and request.project.commtrack_enabled):
        raise Http404()
    return HttpResponseRedirect(default_commtrack_url(domain))


def default_commtrack_url(domain):
    from corehq.apps.products.views import ProductListView
    return reverse(ProductListView.urlname, args=[domain])


class BaseCommTrackManageView(BaseDomainView):
    section_name = ugettext_noop("Setup")

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
    page_title = ugettext_noop("Advanced Settings")
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
    page_title = ugettext_noop("Consumption")

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
    page_title = ugettext_noop("SMS")
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
            'actions': [self._get_action_info(a) for a in self.domain_object.commtrack_settings.actions],
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
        for k, v in six.iteritems(all_sms_codes(self.domain)):
            if v[0] == 'product':
                yield (k, (v[0], v[1].name))

    def post(self, request, *args, **kwargs):
        payload = json.loads(request.POST.get('json'))

        def mk_action(action):
            return CommtrackActionConfig(**{
                    'action': action['type'],
                    'subaction': action['caption'],
                    'keyword': action['keyword'],
                    'caption': action['caption'],
                })

        # TODO add server-side input validation here (currently validated on client)

        self.domain_object.commtrack_settings.actions = [mk_action(a) for a in payload['actions']]
        self.domain_object.commtrack_settings.save()

        return self.get(request, *args, **kwargs)

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(SMSSettingsView, self).dispatch(request, *args, **kwargs)


class StockLevelsView(BaseCommTrackManageView):
    urlname = 'stock_levels'
    page_title = ugettext_noop("Stock Levels")
    template_name = 'commtrack/manage/stock_levels.html'

    @method_decorator(toggles.LOCATION_TYPE_STOCK_RATES.required_decorator())
    def dispatch(self, *args, **kwargs):
        return super(StockLevelsView, self).dispatch(*args, **kwargs)

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
        return StockLevelsForm(data, request=self.request)

    def post(self, request, *args, **kwargs):
        if self.stock_levels_form.is_valid():
            self.save_stock_levels(self.stock_levels_form.cleaned_data)
            return HttpResponseRedirect(self.page_url)
        # TODO display error messages to the user...
        return self.get(request, *args, **kwargs)


class RebuildStockStateView(BaseCommTrackManageView):
    urlname = 'rebuild_stock_state'
    page_title = ugettext_noop("Rebuild Stock State")
    template_name = 'commtrack/manage/rebuild_stock_state.html'

    @memoized
    def get_server_date_by_form_id(self, form_id):
        try:
            server_date = FormAccessors(self.domain).get_form(form_id).received_on
        except XFormNotFound:
            return None
        else:
            return ServerTime(server_date).ui_string()

    def _get_selected_case_id(self):
        location_id = self.request.GET.get('location_id')
        if location_id:
            try:
                return (SQLLocation.objects
                        .get(domain=self.domain, location_id=location_id)
                        .supply_point_id)
            except SQLLocation.DoesNotExist:
                messages.error(self.request, 'Your location id did not match a location')

    @property
    def page_context(self, **kwargs):
        stock_state_limit = int(self.request.GET.get('stock_state_limit', 100))
        stock_transaction_limit = int(self.request.GET.get('stock_transaction_limit', 1000))
        stock_state_limit_exceeded = False
        stock_transaction_limit_exceeded = False

        query = StockTransaction.objects.filter(report__domain=self.domain)
        selected_case_id = self._get_selected_case_id()
        if selected_case_id:
            query = query.filter(case_id=selected_case_id)
        selected_product_id = self.request.GET.get('product_id')
        if selected_product_id:
            query = query.filter(product_id=selected_product_id)

        stock_state_keys = [
            (txn.case_id, txn.section_id, txn.product_id)
            for txn in query
            .order_by('case_id', 'section_id', 'product_id')
            .distinct('case_id', 'section_id', 'product_id')
            [:stock_state_limit]
        ]
        if len(stock_state_keys) >= stock_state_limit:
            stock_state_limit_exceeded = True

        actions_by_stock_state_key = []
        stock_transaction_count = 0
        for stock_state_key in stock_state_keys:
            actions = self.get_actions_by_stock_state_key(*stock_state_key)
            stock_transaction_count += len(actions[1])
            if stock_transaction_count > stock_transaction_limit:
                stock_transaction_limit_exceeded = True
                break
            actions_by_stock_state_key.append(actions)

        assert len(set(stock_state_keys)) == len(stock_state_keys)
        return {
            'actions_by_stock_state_key': actions_by_stock_state_key,
            'stock_state_limit_exceeded': stock_state_limit_exceeded,
            'stock_state_limit': stock_state_limit,
            'stock_transaction_limit_exceeded': stock_transaction_limit_exceeded,
            'stock_transaction_limit': stock_transaction_limit,
        }

    def get_actions_by_stock_state_key(self, case_id, section_id, product_id):
        actions = [
            (
                action.__class__.__name__,
                action,
                self.get_server_date_by_form_id(
                    action.stock_transaction.report.form_id),
            ) for action in
            plan_rebuild_stock_state(case_id, section_id, product_id)
        ]
        return (
            {'case_id': case_id,
             'section_id': section_id,
             'product_id': product_id},
            actions,
            get_doc_info_by_id(self.domain, case_id)
        )

    def post(self, request, *args, **kwargs):
        case_id = request.POST.get('case_id')
        section_id = request.POST.get('section_id')
        product_id = request.POST.get('product_id')
        if None in (case_id, section_id, product_id):
            return HttpResponseBadRequest()
        rebuild_stock_state(case_id, section_id, product_id)
        return HttpResponseRedirect('.')
