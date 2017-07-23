# -*- coding: utf- 8 -*-
import json
from collections import OrderedDict

from django.utils.translation import ugettext_noop
from django.views.generic import TemplateView
from django.core import serializers
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.es import cases as case_es
from corehq.apps.locations.dbaccessors import user_ids_at_locations
from corehq.apps.locations.models import SQLLocation
from corehq.apps.domain.decorators import require_superuser
from custom.rch.forms import BeneficiariesFilterForm
from custom.rch.models import RCHRecord, AreaMapping

ICDS_CAS_DOMAIN = "icds-cas"
RECORDS_PER_PAGE = 200


@method_decorator([toggles.DASHBOARD_ICDS_REPORT.required_decorator(), login_and_domain_required], name='dispatch')
class BeneficariesList(TemplateView):
    urlname = 'rch_cas_dashboard'
    http_method_names = ['get', 'post']

    # ToDo: Check how to set page title. Looks like this is not working
    page_title = ugettext_noop("RCH-CAS Beneficiary list")
    template_name = 'rch/beneficiaries_list.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficariesList, self).dispatch(request, *args, **kwargs)

    def get_rch_records(self):
        self.beneficiaries = RCHRecord.objects
        stcode = self.request.GET.get('stcode')
        if stcode:
            self.beneficiaries = self.beneficiaries.filter(state_id=stcode)
        dcode = self.request.GET.get('dtcode')
        if dcode:
            self.beneficiaries = self.beneficiaries.filter(district_id=dcode)

        # find corresponding village(s) for the selected awc id to search
        # rch records by their village
        awcid = self.request.GET.get('awcid')
        village_code = self.request.GET.get('village_code')
        village_ids = [village_code]
        if awcid:
            village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)
        if village_ids:
            self.beneficiaries = self.beneficiaries.filter(village_id__in=village_ids)

    def get_cas_records(self, awc_ids):
        self.beneficiaries = case_es.CaseES().domain(ICDS_CAS_DOMAIN).size(RECORDS_PER_PAGE)
        awc_loc_ids = list(
            SQLLocation.objects.filter(site_code__in=awc_ids).values_list('location_id', flat=True)
        )
        user_ids = user_ids_at_locations(awc_loc_ids)
        # ToDo: Confirm that this check is correct to include both users and locations
        # ToDo: remove awc_ids added for demo purpose
        user_ids = user_ids + awc_loc_ids + awc_ids
        if user_ids:
            self.beneficiaries = self.beneficiaries.filter(case_es.user(user_ids))
            return self.beneficiaries.run()

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)

        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)

        beneficiaries_in = self.request.GET.get('present_in')
        if beneficiaries_in == 'cas':
            village_code = self.request.GET.get('village_code')
            awc_id = self.request.GET.get('awcid')
            awc_ids = [awc_id] + AreaMapping.fetch_awc_ids_for_village_id(village_code)
            context['beneficiaries'] = []
            if awc_ids:
                cas_records = self.get_cas_records(awc_ids)
                if cas_records:
                    context['beneficiaries'] = cas_records.hits
                    context['beneficiaries_total'] = cas_records.total
                    context['beneficiaries_count'] = len(cas_records.hits)
        elif beneficiaries_in == 'both':
            self.beneficiaries = RCHRecord.objects.exclude(cas_case_id__isnull=True)
        else:
            self.get_rch_records()
            context['beneficiaries_total'] = self.beneficiaries.count()
            context['beneficiaries'] = self.beneficiaries.order_by()[:RECORDS_PER_PAGE]
        return context

    def get_template_names(self):
        if self.request.GET.get('present_in') == 'cas':
            return "cas/beneficiaries_list.html"
        return self.template_name


class BeneficiaryView(TemplateView):
    http_method_names = ['get']
    urlname = 'beneficiary_view'

    page_title = ugettext_noop("RCH-CAS Beneficiary Details")
    template_name = 'rch/beneficiary.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficiaryView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BeneficiaryView, self).get_context_data(**kwargs)
        beneficiary = RCHRecord.objects.get(pk=kwargs.get('beneficiary_id'))
        beneficiary_details = json.loads(serializers.serialize('json', [beneficiary]))[0].get('fields')
        # delete the details dict and include it as details in context
        del beneficiary_details['details']
        beneficiary_details.update(beneficiary.details)
        ordered_beneficiary_details = OrderedDict()
        for detail in sorted(beneficiary_details.iterkeys()):
            ordered_beneficiary_details[detail] = beneficiary_details[detail]
        context['beneficiary_details'] = ordered_beneficiary_details

        return context
