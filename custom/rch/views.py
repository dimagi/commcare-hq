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
    template_name = 'common/beneficiaries_list.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficariesList, self).dispatch(request, *args, **kwargs)

    def _set_rch_beneficiaries(self, include_matched_beneficiaries, only_matched=False):
        """
        Location Hierarchy: State -> District -> Village -> AWC
        Filters down-up Village -> District -> State
        Tries to filters by village_id selected but then falls back to
        district's or state's village id for filtering
        When filtering using AWC id, it looks for the corresponding village id using
        AWC-Village mapping but it would result in beneficiaries from other AWC since
        its many to many mapping.
        :param include_matched_beneficiaries: include matched beneficiaries or
         just render rch records that have no matching CAS record yet
        :param only_matched: filter only matched beneficiaries
        :return: True if it could find records else False
        """
        self.beneficiaries = RCHRecord.objects
        if only_matched:
            # exclude beneficiaries where cas_case_id is null
            self.beneficiaries = self.beneficiaries.exclude(cas_case_id__isnull=True)
        elif not include_matched_beneficiaries:
            # fetch beneficiaries where case_case_id is NOT null
            self.beneficiaries = self.beneficiaries.exclude(cas_case_id__isnull=False)
        village_ids = []

        village_code = self.request.GET.get('village_code')
        if village_code:
            village_ids = village_ids + [village_code]

        # find corresponding village(s) for the selected awc id to search
        # rch records by their village
        awcid = self.request.GET.get('awcid')
        if awcid:
            village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)

        if not village_ids:
            # Fallback to search by district
            dtcode = self.request.GET.get('dtcode')
            if dtcode:
                village_ids = AreaMapping.fetch_village_ids_for_district(dtcode)

        if not village_ids:
            # Fallback to search by state
            stcode = self.request.GET.get('stcode')
            if stcode:
                village_ids = AreaMapping.fetch_village_ids_by_state(stcode)

        if village_ids:
            self.beneficiaries = self.beneficiaries.filter(village_id__in=village_ids)
            return True

        # set beneficiaries empty if unable to filter by any field
        self.beneficiaries = []
        return False

    def _set_cas_beneficiaries(self, include_matched_beneficiaries):
        """
        Location Hierarchy: State -> District -> Village -> AWC
        Filters down-up AWC -> Village -> District -> State
        Filters by AWC id present as owner in cas records.
        Tries to filters by AWC id selected or AWCs under village ID selected but then falls back to
        district's or state's AWC ids for filtering
        When filtering using Village id, it looks for the corresponding AWC ids using
        AWC-Village mapping but it would result in beneficiaries from other Village since
        its many to many mapping.
        :param include_matched_beneficiaries: to include matched beneficiaries or
         just render rch records excluding the ones that have been matched
        :return: True if it could find records else False
        """
        self.beneficiaries = case_es.CaseES().domain(ICDS_CAS_DOMAIN).size(RECORDS_PER_PAGE)
        if not include_matched_beneficiaries:
            self.beneficiaries = self.beneficiaries.filter(case_es.missing('rch_record_id'))
        awc_ids = []

        # find corresponding awc_id(s) for the selected village id to search
        # cas records by their awc_ids set as owner_id
        village_code = self.request.GET.get('village_code')
        if village_code:
            awc_ids = awc_ids + AreaMapping.fetch_awc_ids_for_village_id(village_code)

        awc_id = self.request.GET.get('awcid')
        if awc_id:
            awc_ids = awc_ids + [awc_id]

        # if no village or awc then simply filter by all AWC IDs under the district
        if not awc_ids:
            dtcode = self.request.GET.get('dtcode')
            if dtcode:
                awc_ids = AreaMapping.fetch_awc_ids_for_district(dtcode)

        # if no village or awc then simply filter by all AWC IDs under the state
        if not awc_ids:
            stcode = self.request.GET.get('stcode')
            if stcode:
                awc_ids = AreaMapping.fetch_awc_ids_for_state(stcode)

        if awc_ids:
            awc_loc_ids = list(
                SQLLocation.objects.filter(site_code__in=awc_ids).values_list('location_id', flat=True)
            )
            user_ids = user_ids_at_locations(awc_loc_ids)
            # ToDo: Confirm that this check is correct to include both users and locations
            # ToDo: remove awc_ids added for demo purpose
            user_ids = user_ids + awc_loc_ids + awc_ids
            if user_ids:
                self.beneficiaries = self.beneficiaries.filter(case_es.user(user_ids))
                return True

        # set beneficiaries empty if unable to filter by any awc_id
        self.beneficiaries = []
        return False

    def _set_context_for_cas_records(self, context):
        include_matched_beneficiaries = (self.request.GET.get('matched') == 'on')
        if self._set_cas_beneficiaries(include_matched_beneficiaries):
            cas_records = self.beneficiaries.run()
            if cas_records:
                context['beneficiaries'] = cas_records.hits
                context['beneficiaries_total'] = cas_records.total
                context['beneficiaries_count'] = len(cas_records.hits)

    def _set_context_for_rch_records(self, context):
        include_matched_beneficiaries = (self.request.GET.get('matched') == 'on')
        if self._set_rch_beneficiaries(include_matched_beneficiaries):
            context['beneficiaries_total'] = self.beneficiaries.count()
            context['beneficiaries'] = self.beneficiaries.order_by()[:RECORDS_PER_PAGE]

    def _set_context_for_matched_records(self, context):
        self.beneficiaries = RCHRecord.objects.exclude(cas_case_id__isnull=True)
        if self._set_rch_beneficiaries(True, only_matched=True):
            context['beneficiaries_total'] = self.beneficiaries.count()
            context['beneficiaries'] = self.beneficiaries.order_by()[:RECORDS_PER_PAGE]

    def _set_beneficiaries(self, context, present_in):
        context['beneficiaries'] = []
        if present_in == 'cas':
            self._set_context_for_cas_records(context)
        elif present_in == 'rch':
            self._set_context_for_rch_records(context)
        elif present_in == 'both':
            self._set_context_for_matched_records(context)

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)
        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)
        present_in = beneficiaries_in = self.request.GET.get('present_in')
        if present_in:
            self._set_beneficiaries(context, present_in)
        return context

    def get_template_names(self):
        if self.request.GET.get('present_in') == 'cas':
            return "cas/beneficiaries_list.html"
        elif self.request.GET.get('present_in') == 'rch':
            return "rch/beneficiaries_list.html"
        elif self.request.GET.get('present_in') == 'both':
            return "common/beneficiaries_list.html"
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
