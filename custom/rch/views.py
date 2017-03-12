import json

from django.utils.translation import ugettext_noop
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import TemplateView
from django.core import serializers
from django.utils.decorators import method_decorator
from django.core.urlresolvers import reverse, reverse_lazy
from django.views.generic import UpdateView

from corehq.apps.domain.decorators import require_superuser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.rch.forms import BeneficiariesFilterForm, CreateMotherFieldMappingForm, CreateChildFieldMappingForm
from custom.rch.models import RCHMother, RCHChild, MotherFieldMapping, ChildFieldMapping


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

        context['filter_form'] = BeneficiariesFilterForm(data=self.request.GET, domain=self.request.domain)

        mother_beneficiaries = RCHMother.objects
        child_beneficiaries = RCHChild.objects

        state = self.request.GET.get('state')
        if state:
            mother_beneficiaries = mother_beneficiaries.filter(State_Name=state)
            child_beneficiaries = child_beneficiaries.filter(State_Name=state)
        district = self.request.GET.get('district')
        if district:
            mother_beneficiaries = mother_beneficiaries.filter(District_Name=district)
            child_beneficiaries = child_beneficiaries.filter(District_Name=district)

        # To be included once mapping is available
        # awcid = self.request.GET.get('awcid')
        # village_id = self.request.GET.get('village_id')
        # village_ids = [village_id]
        # if awcid:
        #     village_ids = village_ids + AreaMapping.fetch_village_ids_for_awcid(awcid)
        #
        # if village_ids:
        #     mother_beneficiaries = mother_beneficiaries.filter(MDDS_VillageID__in=village_ids)
        #     child_beneficiaries = child_beneficiaries.filter(MDDS_VillageID__in=village_ids)

        village_name = self.request.GET.get('village_name')
        if village_name:
            mother_beneficiaries = mother_beneficiaries.filter(Village_Name__contains=village_name)
            child_beneficiaries = child_beneficiaries.filter(Village_Name__contains=village_name)

        context['mother_beneficiaries_total'] = mother_beneficiaries.count()
        context['child_beneficiaries_total'] = child_beneficiaries.count()
        context['mother_beneficiaries'] = mother_beneficiaries.order_by()[:20]
        context['child_beneficiaries'] = child_beneficiaries.order_by()[:20]

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
        self.beneficiary = RCHMother.objects.get(pk=kwargs.get('beneficiary_id'))
        beneficiary = serializers.serialize('json', [self.beneficiary])
        context['beneficiary_details'] = json.loads(beneficiary)[0].get('fields')

        if self.beneficiary.icds_case_id:
            context['rch_priority_fields'] = RCH_PRIORITY_FIELDS
            self.cas_beneficiary = CaseAccessors(domain='icds-cas').get_case(self.beneficiary.icds_case_id)
            context['cas_beneficiary'] = self.cas_beneficiary.dynamic_case_properties()

        return context

    def get_template_names(self):
        default = super(MotherBeneficiaryView, self).get_template_names()
        if self.beneficiary.icds_case_id:
            return ['rch/consolidated_beneficiary_details.html']
        return default


class ChildBeneficiaryView(BeneficiaryView):
    urlname = 'child_beneficiary_view'

    def get_context_data(self, **kwargs):
        context = super(BeneficiaryView, self).get_context_data(**kwargs)
        self.beneficiary = RCHChild.objects.get(pk=kwargs.get('beneficiary_id'))
        beneficiary = serializers.serialize('json', [self.beneficiary])
        context['beneficiary_details'] = json.loads(beneficiary)[0].get('fields')
        return context


class MotherFieldMappingCreateView(CreateView):
    urlname = 'create_mother_field_mapping'
    model = MotherFieldMapping
    template_name = 'rch/field_mapping.html'
    fields = ['rch_field', 'cas_case_type', 'cas_case_field']

    def get_success_url(self):
        return reverse_lazy('create_mother_field_mapping', args=[self.request.domain])

    def get_context_data(self, **kwargs):
        context = super(MotherFieldMappingCreateView, self).get_context_data(**kwargs)
        context['field_mapping_form'] = CreateMotherFieldMappingForm()
        context['field_mappings'] = MotherFieldMapping.objects.all()
        context['beneficiary_type'] = 'Mother'
        context['domain'] = self.request.domain
        context['update_url'] = 'update_mother_field_mapping'
        context['delete_url'] = 'delete_mother_field_mapping'
        return context


class ChildFieldMappingCreateView(CreateView):
    urlname = 'create_child_field_mapping'
    model = ChildFieldMapping
    template_name = 'rch/field_mapping.html'
    fields = ['rch_field', 'cas_case_type', 'cas_case_field']

    def get_success_url(self):
        return reverse_lazy('create_child_field_mapping', args=[self.request.domain])

    def get_context_data(self, **kwargs):
        context = super(ChildFieldMappingCreateView, self).get_context_data(**kwargs)
        context['field_mapping_form'] = CreateChildFieldMappingForm()
        context['field_mappings'] = ChildFieldMapping.objects.all()
        context['beneficiary_type'] = 'Child'
        context['domain'] = self.request.domain
        context['update_url'] = 'update_child_field_mapping'
        context['delete_url'] = 'delete_child_field_mapping'
        return context


class MotherFieldMappingUpdateView(UpdateView):
    urlname = 'update_mother_field_mapping'
    model = MotherFieldMapping
    template_name = 'rch/field_mapping_edit.html'
    fields = ['rch_field', 'cas_case_type', 'cas_case_field']

    def get_success_url(self):
        return reverse_lazy('create_mother_field_mapping', args=[self.request.domain])

    def get_context_data(self, **kwargs):
        context = super(MotherFieldMappingUpdateView, self).get_context_data(**kwargs)
        context['field_mapping_form'] = CreateMotherFieldMappingForm(
            json.loads(serializers.serialize('json', [context['object']]))[0]['fields'])
        context['beneficiary_type'] = 'Mother'
        context['domain'] = self.request.domain
        return context


class ChildFieldMappingUpdateView(UpdateView):
    urlname = 'update_child_field_mapping'
    model = ChildFieldMapping
    template_name = 'rch/field_mapping_edit.html'
    fields = ['rch_field', 'cas_case_type', 'cas_case_field']

    def get_success_url(self):
        return reverse_lazy('create_child_field_mapping', args=[self.request.domain])

    def get_context_data(self, **kwargs):
        context = super(ChildFieldMappingUpdateView, self).get_context_data(**kwargs)
        context['field_mapping_form'] = CreateChildFieldMappingForm(
            json.loads(serializers.serialize('json', [context['object']]))[0]['fields'])
        context['beneficiary_type'] = 'Child'
        context['domain'] = self.request.domain
        return context


class MotherFieldMappingDeleteView(DeleteView):
    urlname = 'delete_mother_field_mapping'
    model = MotherFieldMapping

    def get_success_url(self):
        return reverse_lazy('create_mother_field_mapping', args=[self.request.domain])


class ChildFieldMappingDeleteView(DeleteView):
    urlname = 'delete_child_field_mapping'
    model = ChildFieldMapping

    def get_success_url(self):
        return reverse_lazy('create_child_field_mapping', args=[self.request.domain])