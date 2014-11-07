from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from corehq.apps.commtrack.util import all_sms_codes
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
)
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import Product, Program
from corehq.apps.commtrack.forms import ProgramForm, ConsumptionForm
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location
from dimagi.utils.decorators.memoized import memoized
from django.core.urlresolvers import reverse
from django.contrib import messages
from corehq.apps.commtrack.tasks import recalculate_domain_consumption_task
import json
from couchdbkit import ResourceNotFound
import itertools
import copy
from dimagi.utils.web import json_response


@domain_admin_required
def default(request, domain):
    from corehq.apps.products.views import ProductListView
    if not (request.project and request.project.commtrack_enabled):
        raise Http404()
    return HttpResponseRedirect(reverse(ProductListView.urlname,
                                        args=[domain]))


class BaseCommTrackManageView(BaseDomainView):
    section_name = ugettext_noop("Setup")

    @property
    def section_url(self):
        return reverse('default_commtrack_setup', args=[self.domain])

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
        from corehq.apps.commtrack.forms import CommTrackSettingsForm
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

        from corehq.apps.commtrack.models import StockRestoreConfig
        if self.commtrack_settings.sync_consumption_fixtures:
            self.domain_object.commtrack_settings.ota_restore_config = StockRestoreConfig(
                section_to_consumption_types={
                    'stock': 'consumption'
                },
                force_consumption_case_types=[
                    'supply-point'
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
            self.commtrack_settings.sync_location_fixtures = bool(data.get('sync_location_fixtures'))
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


@require_POST
@domain_admin_required
def delete_program(request, domain, prog_id):
    program = Program.get(prog_id)
    program.delete()
    return json_response({
        'success': True,
        'message': _("Program '{program_name}' has successfully been deleted.").format(
            program_name=program.name,
        )
    })


@login_and_domain_required
def api_query_supply_point(request, domain):
    id = request.GET.get('id')
    query = request.GET.get('name', '')
    
    def loc_to_payload(loc):
        return {'id': loc._id, 'name': loc.name}

    if id:
        try:
            loc = Location.get(id)
            return HttpResponse(json.dumps(loc_to_payload(loc)), 'text/json')

        except ResourceNotFound:
            return HttpResponseNotFound(json.dumps({'message': 'no location with is %s found' % id}, 'text/json'))

    else:
        LIMIT = 100
        loc_types = [loc_type.name for loc_type in Domain.get_by_name(domain).commtrack_settings.location_types if not loc_type.administrative]

        def get_locs(type):
            # TODO use ES instead?
            q = query.lower()
            startkey = [domain, type, q]
            endkey = [domain, type, q + 'zzzzzz']
            return [loc for loc in Location.view(
                'locations/by_name',
                startkey=startkey,
                endkey=endkey,
                limit=LIMIT,
                reduce=False,
                include_docs=True,
            ) if not loc.is_archived]

        locs = sorted(
            itertools.chain(*(get_locs(loc_type) for loc_type in loc_types)),
            key=lambda e: e.name
        )[:LIMIT]
        return HttpResponse(json.dumps(map(loc_to_payload, locs)), 'text/json')


class ProgramListView(BaseCommTrackManageView):
    urlname = 'commtrack_program_list'
    template_name = 'commtrack/manage/programs.html'
    page_title = ugettext_noop("Programs")


class FetchProgramListView(ProgramListView):
    urlname = 'commtrack_program_fetch'

    @property
    def program_data(self):
        data = []
        programs = Program.by_domain(self.domain)
        for p in programs:
            info = p._doc
            info['is_default'] = info.pop('default')
            info['edit_url'] = reverse('commtrack_program_edit', kwargs={'domain': self.domain, 'prog_id': p._id})
            info['delete_url'] = reverse('delete_program', kwargs={'domain': self.domain, 'prog_id': p._id})
            data.append(info)
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'data_list': self.program_data,
        }), 'text/json')


class NewProgramView(BaseCommTrackManageView):
    urlname = 'commtrack_program_new'
    page_title = ugettext_noop("New Program")
    template_name = 'commtrack/manage/program.html'

    @property
    @memoized
    def program(self):
        return Program(domain=self.domain)

    @property
    def parent_pages(self):
        return [{
            'title': ProgramListView.page_title,
            'url': reverse(ProgramListView.urlname, args=[self.domain]),
        }]

    @property
    @memoized
    def new_program_form(self):
        if self.request.method == 'POST':
            return ProgramForm(self.program, self.request.POST)
        return ProgramForm(self.program)

    @property
    def page_context(self):
        return {
            'program': self.program,
            'form': self.new_program_form,
        }

    def post(self, request, *args, **kwargs):
        if self.new_program_form.is_valid():
            self.new_program_form.save()
            messages.success(request, _("Program saved!"))
            return HttpResponseRedirect(reverse(ProgramListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class EditProgramView(NewProgramView):
    urlname = 'commtrack_program_edit'
    page_title = ugettext_noop("Edit Program")

    DEFAULT_LIMIT = 10

    @property
    def page(self):
        return self.request.GET.get('page', 1)

    @property
    def limit(self):
        return self.request.GET.get('limit', self.DEFAULT_LIMIT)

    @property
    def total(self):
        return len(Product.by_program_id(self.domain, self.program_id))

    @property
    def page_context(self):
        return {
            'program': self.program,
            'data_list': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total
            },
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT),
            'form': self.new_program_form,
        }

    @property
    def program_id(self):
        try:
            return self.kwargs['prog_id']
        except KeyError:
            raise Http404()

    @property
    @memoized
    def program(self):
        try:
            return Program.get(self.program_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def page_name(self):
        return _("Edit %s") % self.program.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.program_id])


class FetchProductForProgramListView(EditProgramView):
    urlname = 'commtrack_product_for_program_fetch'

    def skip(self):
        return (int(self.page) - 1) * int(self.limit)

    @property
    def product_data(self):
        def _scrub(product_doc):
            product_doc['code'] = product_doc.pop('code_')
            return product_doc

        data = []
        products = Product.by_program_id(domain=self.domain, prog_id=self.program_id, skip=self.skip(),
                limit=self.limit)
        for p in products:
            data.append(_scrub(p._doc))
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': self.page,
            'data_list': self.product_data,
        }), 'text/json')


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
        from corehq.apps.commtrack.models import CommtrackActionConfig

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
