import json

from django.utils.translation import ugettext_noop
from django.views.generic import TemplateView
from django.core import serializers
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import require_superuser
from custom.rch.forms import BeneficiariesFilterForm
from custom.rch.models import RCHMother, AreaMapping, RCHChild


class BeneficariesList(TemplateView):
    urlname = 'beneficiaries_list'
    http_method_names = ['get', 'post']

    page_title = ugettext_noop("RCH-CAS Beneficiary list")
    template_name = 'rch/beneficiaries_list.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BeneficariesList, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)
        context['filter_form'] = BeneficiariesFilterForm()

        mother_beneficiaries = RCHMother.objects
        child_beneficiaries = RCHChild.objects

        context['mother_beneficiaries'] = mother_beneficiaries.all()
        context['child_beneficiaries'] = child_beneficiaries.all()

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()
        mother_beneficiaries = RCHMother.objects
        child_beneficiaries = RCHChild.objects
        state = request.POST.get('state')
        if state:
            mother_beneficiaries = mother_beneficiaries.filter(State_Name=state)
            child_beneficiaries = child_beneficiaries.filter(State_Name=state)
        district = request.POST.get('district')
        if district:
            mother_beneficiaries = mother_beneficiaries.filter(District_Name=district)
            child_beneficiaries = child_beneficiaries.filter(District_Name=district)

        # To be included once mapping is available
        # awcid = request.POST.get('awcid')
        # village_id = request.POST.get('village_id')
        # village_ids = [village_id]
        # if awcid:
        #     village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)
        #
        # if village_ids:
        #     mother_beneficiaries = mother_beneficiaries.filter(MDDS_VillageID__in=village_ids)
        #     child_beneficiaries = child_beneficiaries.filter(MDDS_VillageID__in=village_ids)

        village_name = request.POST.get('village_name')
        if village_name:
            mother_beneficiaries = mother_beneficiaries.filter(Village_Name__contains=village_name)
            child_beneficiaries = child_beneficiaries.filter(VILLAGE_Name__contains=village_name)
        context['mother_beneficiaries'] = mother_beneficiaries.all()
        context['child_beneficiaries'] = child_beneficiaries.all()
        return super(TemplateView, self).render_to_response(context)


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
