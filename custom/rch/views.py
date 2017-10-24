# -*- coding: utf- 8 -*-
import json
from collections import OrderedDict

from django.urls import reverse
from django.utils.translation import ugettext_noop
from django.core import serializers
from django.utils.decorators import method_decorator

from corehq.apps.domain.views import BaseDomainView
from corehq.apps.reports.views import CaseDetailsView
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from djangular.views.mixins import (
    JSONResponseMixin,
    allow_remote_invocation,
)

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.es import cases as case_es
from corehq.apps.locations.dbaccessors import user_ids_at_locations
from corehq.apps.locations.models import SQLLocation
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.decorators import use_select2, use_angular_js
from custom.rch.forms import BeneficiariesFilterForm
from custom.rch.models import RCHChildRecord, RCHMotherRecord, AreaMapping
from custom.rch.templatetags.view_tags import mask_aadhar_number
from custom.rch.utils import (
    valid_aadhar_num_length,
)
from custom.rch.const import (
    ICDS_CAS_DOMAIN,
    RECORDS_PER_PAGE,
    AADHAR_NUM_FIELDS,
    RCH_PERMITTED_FIELD_MAPPINGS,

)


@method_decorator([toggles.VIEW_CAS_RCH_REPORTS.required_decorator(),
                   login_and_domain_required], name='dispatch')
class BeneficariesList(JSONResponseMixin, BaseDomainView):
    urlname = 'rch_cas_dashboard'
    http_method_names = ['get', 'post']

    # ToDo: Check how to set page title. Looks like this is not working
    page_title = ugettext_noop("RCH-CAS Beneficiary list")
    template_name = 'rch/beneficiaries_list.html'

    def section_url(self):
        return reverse(self.urlname, args=[ICDS_CAS_DOMAIN])

    @method_decorator(require_superuser)
    @use_select2
    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        response = super(BeneficariesList, self).dispatch(request, *args, **kwargs)
        # set cookie for pagination
        response.set_cookie('hq.pagination.limit.rch_cas_beneficiaries.%s' % request.domain, RECORDS_PER_PAGE)
        return response

    @staticmethod
    def _get_rch_beneficiaries(include_matched_beneficiaries, in_data, only_matched=False):
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
        beneficiary_type = in_data.get('beneficiary_type')
        if beneficiary_type == 'child':
            beneficiaries = RCHChildRecord.objects
        else:
            beneficiaries = RCHMotherRecord.objects
        if only_matched:
            # exclude beneficiaries where cas_case_id is null
            beneficiaries = beneficiaries.exclude(cas_case_id__isnull=True)
        elif not include_matched_beneficiaries:
            # fetch beneficiaries where case_case_id is NOT null
            beneficiaries = beneficiaries.exclude(cas_case_id__isnull=False)
        village_ids = []

        village_code = in_data.get('village_code')
        if village_code:
            village_ids = [village_code]

        # find corresponding village(s) for the selected awc id to search
        # rch records by their village
        awcid = in_data.get('awcid')
        if awcid:
            village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)

        if not village_ids:
            # Fallback to search by district
            dtcode = in_data.get('dtcode')
            if dtcode:
                village_ids = AreaMapping.fetch_village_ids_for_district(dtcode)

        if not village_ids:
            # Fallback to search by state
            stcode = in_data.get('stcode')
            if stcode:
                village_ids = AreaMapping.fetch_village_ids_for_state(stcode)

        if village_ids:
            return beneficiaries.filter(village_id__in=village_ids)

    @staticmethod
    def _get_cas_beneficiaries(include_matched_beneficiaries, in_data=None):
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
        beneficiaries = case_es.CaseES().domain(ICDS_CAS_DOMAIN).size(RECORDS_PER_PAGE)
        if not include_matched_beneficiaries:
            beneficiaries = beneficiaries.filter(case_es.missing('rch_record_id'))
        awc_ids = []

        # find corresponding awc_id(s) for the selected village id to search
        # cas records by their awc_ids set as owner_id
        village_code = in_data.get('village_code')
        if village_code:
            awc_ids = AreaMapping.fetch_awc_ids_for_village_id(village_code)

        awc_id = in_data.get('awcid')
        if awc_id:
            awc_ids = awc_ids + [awc_id]

        # if no village or awc then simply filter by all AWC IDs under the district
        if not awc_ids:
            dtcode = in_data.get('dtcode')
            if dtcode:
                awc_ids = AreaMapping.fetch_awc_ids_for_district(dtcode)

        # if no village or awc then simply filter by all AWC IDs under the state
        if not awc_ids:
            stcode = in_data.get('stcode')
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
                return beneficiaries.user(user_ids)

    def _set_context_for_cas_records(self, context, in_data=None):
        include_matched_beneficiaries = (in_data.get('matched') == 'on')
        size = in_data.get('limit')
        offset = (in_data.get('page') - 1) * in_data.get('limit')
        beneficiaries = self._get_cas_beneficiaries(include_matched_beneficiaries, in_data=in_data)
        if beneficiaries:
            cas_records = beneficiaries.start(offset).size(size).run()
            total_cas_records = cas_records.total
            if total_cas_records:
                context['beneficiaries'] = cas_records.hits
                context['beneficiaries_total'] = total_cas_records
                context['beneficiaries_count'] = len(cas_records.hits)

    def _set_context_for_rch_records(self, context, in_data=None):
        include_matched_beneficiaries = (in_data.get('matched') == 'on')
        size = in_data.get('limit')
        offset = (in_data.get('page') - 1) * in_data.get('limit')
        beneficiaries = self._get_rch_beneficiaries(include_matched_beneficiaries, in_data)
        if beneficiaries:
            context['beneficiaries_total'] = beneficiaries.count()
            context['beneficiaries'] = beneficiaries.order_by('-last_modified')[offset:offset + size]

    def _set_context_for_matched_records(self, context, in_data=None):
        beneficiaries = self._get_rch_beneficiaries(True, in_data, only_matched=True)
        if beneficiaries:
            size = in_data.get('limit')
            offset = (in_data.get('page') - 1) * in_data.get('limit')
            context['beneficiaries_total'] = beneficiaries.count()
            context['beneficiaries'] = beneficiaries[offset:offset + size]

    def _set_beneficiaries(self, context, in_data):
        context['beneficiaries'] = []
        present_in = in_data.get('present_in')
        if present_in == 'cas':
            self._set_context_for_cas_records(context, in_data)
        elif present_in == 'rch':
            self._set_context_for_rch_records(context, in_data)
        elif present_in == 'both':
            self._set_context_for_matched_records(context, in_data)

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)
        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)
        context['pagination_limit_cookie_name'] = ('hq.pagination.limit.rch_cas_beneficiaries.%s'
                                                   % self.request.domain)
        return context

    def get_template_names(self):
        if self.request.GET.get('present_in') == 'cas':
            return "cas/beneficiaries_list.html"
        return self.template_name

    @staticmethod
    def _mask_aadhar_number(beneficiary_json):
        for aadhar_num_field in AADHAR_NUM_FIELDS:
            if beneficiary_json.get(aadhar_num_field):
                beneficiary_json[aadhar_num_field] = mask_aadhar_number(beneficiary_json[aadhar_num_field])

    def _format_beneficiary(self, beneficiary):
        beneficiary_json = json.loads(serializers.serialize('json', [beneficiary]))[0].get('fields')
        beneficiary_json['editUrl'] = reverse(
            BeneficiaryView.urlname,
            args=[ICDS_CAS_DOMAIN,
                  beneficiary.beneficiary_type,
                  beneficiary.id])
        self._mask_aadhar_number(beneficiary_json)
        return beneficiary_json

    @allow_remote_invocation
    def get_pagination_data(self, in_data):
        context = {}
        if in_data.get('present_in'):
            self._set_beneficiaries(context, in_data)

        if in_data.get('present_in') == 'cas':
            itemList = context.get('beneficiaries')
            for item in itemList:
                item['editUrl'] = reverse(CaseDetailsView.urlname, args=(ICDS_CAS_DOMAIN, item.get('_id')))
                if item.get('aadhar_number'):
                    item['aadhar_number'] = mask_aadhar_number(item['aadhar_number'])
        else:
            itemList = map(lambda beneficiary: self._format_beneficiary(beneficiary),
                           context.get('beneficiaries'))
        return {
            'response': {
                'itemList': itemList,
                'total': context.get('beneficiaries_total', 0),
                'page': in_data.get('page'),
            },
            'success': True,
        }


@method_decorator([toggles.VIEW_CAS_RCH_REPORTS.required_decorator(),
                   login_and_domain_required, require_superuser], name='dispatch')
class BeneficiaryView(BaseDomainView):
    http_method_names = ['get']
    urlname = 'beneficiary_view'

    page_title = ugettext_noop("RCH-CAS Beneficiary Details")
    template_name = 'rch/beneficiary.html'

    def section_url(self):
        return reverse(self.urlname, args=[ICDS_CAS_DOMAIN, self.beneficiary_type, self.beneficiary_id])

    def page_url(self):
        return reverse(self.urlname, args=[ICDS_CAS_DOMAIN, self.beneficiary_type, self.beneficiary_id])

    def dispatch(self, request, *args, **kwargs):
        self.beneficiary_id = kwargs.get('beneficiary_id')
        self.beneficiary_type = kwargs.get('beneficiary_type')
        return super(BeneficiaryView, self).dispatch(request, *args, **kwargs)

    def _get_cas_values(self, details, beneficiary_type, person_case_id):
        person_case = CaseAccessors('icds-cas').get_case(person_case_id)
        if person_case:
            person_case_properties = person_case.dynamic_case_properties()
            field_mappings = RCH_PERMITTED_FIELD_MAPPINGS[beneficiary_type]
            for case_type in field_mappings:
                if case_type == 'person':
                    for rch_field, cas_field in field_mappings[case_type].items():
                        details[rch_field] = [(details[rch_field], person_case_properties.get(cas_field))]
        return details

    def get_context_data(self, **kwargs):
        context = super(BeneficiaryView, self).get_context_data(**kwargs)
        if self.beneficiary_type == 'child':
            beneficiary = RCHChildRecord.objects.get(pk=kwargs.get('beneficiary_id'))
        else:
            beneficiary = RCHMotherRecord.objects.get(pk=kwargs.get('beneficiary_id'))
        beneficiary_details = json.loads(serializers.serialize('json', [beneficiary]))[0].get('fields')
        # delete the details dict and include it as details in context
        del beneficiary_details['details']
        beneficiary_details.update(beneficiary.details)
        if beneficiary.cas_case_id:
            beneficiary_details = self._get_cas_values(beneficiary_details, beneficiary.beneficiary_type,
                                                       beneficiary.cas_case_id)
        ordered_beneficiary_details = OrderedDict()
        # 1. order the details according to detail name
        # 2. if its not a list i.e if corr. value for cas has not been added then
        #    add "N/A"
        for detail in sorted(beneficiary_details.iterkeys()):
            detail_value = beneficiary_details[detail]
            if not isinstance(detail_value, list):
                detail_value = [(detail_value, 'N/A')]
            ordered_beneficiary_details[detail] = detail_value
        for aadhar_num_field in AADHAR_NUM_FIELDS:
            if ordered_beneficiary_details.get(aadhar_num_field):
                for rch_aadhar_num, cas_aadhar_num in ordered_beneficiary_details[aadhar_num_field]:
                    if rch_aadhar_num and valid_aadhar_num_length(rch_aadhar_num):
                        rch_aadhar_num = mask_aadhar_number(rch_aadhar_num)
                    if cas_aadhar_num and valid_aadhar_num_length(cas_aadhar_num):
                        cas_aadhar_num = mask_aadhar_number(cas_aadhar_num)
                    ordered_beneficiary_details[aadhar_num_field] = [(rch_aadhar_num, cas_aadhar_num)]
        context['beneficiary_details'] = ordered_beneficiary_details

        return context
