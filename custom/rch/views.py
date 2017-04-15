import json

from django.utils.translation import ugettext_noop
from django.views.generic import TemplateView
from django.core import serializers
from django.utils.decorators import method_decorator

from corehq.apps.domain.decorators import require_superuser
from custom.rch.forms import BeneficiariesFilterForm
from custom.rch.models import RCHRecord


class BeneficariesList(TemplateView):
    urlname = 'beneficiaries_list'
    http_method_names = ['get', 'post']

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

        village_code = self.request.GET.get('village_code')
        if village_code:
            self.beneficiaries = self.beneficiaries.filter(village_id=village_code)

    def get_cas_records(self):
        self.beneficiaries = RCHRecord.objects.none()

    def get_context_data(self, **kwargs):
        context = super(BeneficariesList, self).get_context_data(**kwargs)

        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)

        beneficiaries_in = self.request.GET.get('present_in')
        if beneficiaries_in == 'cas':
            self.get_cas_records()
        elif beneficiaries_in == 'both':
            self.beneficiaries = RCHRecord.objects.exclude(cas_case_id__isnull=True)
        else:
            self.get_rch_records()
        context['beneficiaries_total'] = self.beneficiaries.count()
        context['beneficiaries'] = self.beneficiaries.order_by()[:20]
        return context


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
        context['beneficiary_details'] = json.loads(serializers.serialize('json', [beneficiary]))[0].get('fields')
        context['beneficiary_details'].update(beneficiary.prop_doc['details'])
        return context
