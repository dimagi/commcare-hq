import json

from django.utils.translation import ugettext_noop
from django.views.generic import TemplateView
from django.core import serializers
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import require_superuser
from custom.rch.forms import BeneficiariesFilterForm
from custom.rch.models import RCHMother, RCHChild


class BeneficariesList(TemplateView):
    urlname = 'beneficiaries_list'
    http_method_names = ['get', 'post']

    page_title = ugettext_noop("RCH-CAS Beneficiary list")
    template_name = 'rch/beneficiaries_list.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficariesList, self).dispatch(request, *args, **kwargs)

    def get_rch_records(self):
        state = self.request.GET.get('state')
        if state:
            self.mother_beneficiaries = self.mother_beneficiaries.filter(State_Name=state)
            self.child_beneficiaries = self.child_beneficiaries.filter(State_Name=state)
        district = self.request.GET.get('district')
        if district:
            self.mother_beneficiaries = self.mother_beneficiaries.filter(District_Name=district)
            self.child_beneficiaries = self.child_beneficiaries.filter(District_Name=district)

        # To be included once mapping is available
        # awcid = self.request.GET.get('awcid')
        # village_id = self.request.GET.get('village_id')
        # village_ids = [village_id]
        # if awcid:
        #     village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)
        #
        # if village_ids:
        #     self.mother_beneficiaries = self.mother_beneficiaries.filter(MDDS_VillageID__in=village_ids)
        #     self.child_beneficiaries = self.child_beneficiaries.filter(MDDS_VillageID__in=village_ids)

        village_name = self.request.GET.get('village_name')
        if village_name:
            self.mother_beneficiaries = self.mother_beneficiaries.filter(Village_Name__contains=village_name)
            self.child_beneficiaries = self.child_beneficiaries.filter(Village_Name__contains=village_name)

    def get_cas_records(self):
        self.mother_beneficiaries = self.mother_beneficiaries.none()
        self.child_beneficiaries = self.child_beneficiaries.none()

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)

        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)

        self.mother_beneficiaries = RCHMother.objects
        self.child_beneficiaries = RCHChild.objects

        beneficiaries_in = self.request.GET.get('present_in')
        if beneficiaries_in == 'both':
            self.mother_beneficiaries = self.mother_beneficiaries.exclude(cas_case_id__isnull=True)
            self.child_beneficiaries = self.child_beneficiaries.exclude(cas_case_id__isnull=True)
        elif beneficiaries_in == 'rch':
            self.get_rch_records()
        elif beneficiaries_in == 'cas':
            self.get_cas_records()

        context['mother_beneficiaries_total'] = self.mother_beneficiaries.count()
        context['child_beneficiaries_total'] = self.child_beneficiaries.count()
        context['mother_beneficiaries'] = self.mother_beneficiaries.order_by()[:20]
        context['child_beneficiaries'] = self.child_beneficiaries.order_by()[:20]


        return context


class BeneficiaryView(TemplateView):
    http_method_names = ['get']

    page_title = ugettext_noop("RCH-CAS Beneficiary Details")
    template_name = 'rch/beneficiary.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficiaryView, self).dispatch(request, *args, **kwargs)


class MotherBeneficiaryView(BeneficiaryView):
    urlname = 'mother_beneficiary_view'

    def get_context_data(self, **kwargs):
        context = super(BeneficiaryView, self).get_context_data(**kwargs)
        beneficiary = serializers.serialize('json', [RCHMother.objects.get(pk=kwargs.get('beneficiary_id'))])
        context['beneficiary_details'] = json.loads(beneficiary)[0].get('fields')
        return context


class ChildBeneficiaryView(BeneficiaryView):
    urlname = 'child_beneficiary_view'

    def get_context_data(self, **kwargs):
        context = super(BeneficiaryView, self).get_context_data(**kwargs)
        beneficiary = serializers.serialize('json', [RCHChild.objects.get(pk=kwargs.get('beneficiary_id'))])
        context['beneficiary_details'] = json.loads(beneficiary)[0].get('fields')
        return context
