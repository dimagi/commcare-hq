from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.util import ErrorList
from corehq.apps.crud.models import BaseAdminCRUDForm
from corehq.apps.indicators.models import FormDataAliasIndicatorDefinition, FormLabelIndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataInCaseIndicatorDefinition, CouchIndicatorDef, CountUniqueCouchIndicatorDef, MedianCouchIndicatorDef, CombinedCouchViewIndicatorDefinition, SumLastEmittedCouchIndicatorDef, DynamicIndicatorDefinition
from dimagi.utils.decorators.memoized import memoized


class BaseIndicatorDefinitionForm(BaseAdminCRUDForm):
    slug = forms.SlugField(label="Slug")
    namespace = forms.CharField(label="Namespace", widget=forms.Select(choices=[]))
    version = forms.IntegerField(label="Version No.")

    namespace_map = "INDICATOR_NAMESPACES"

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None, domain=None):
        super(BaseIndicatorDefinitionForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
                                                          label_suffix, empty_permitted, doc_id)
        self.domain = domain
        available_namespaces = getattr(settings, self.namespace_map, {})
        self.fields['namespace'].widget = forms.Select(choices=available_namespaces.get(self.domain, ()))

    @property
    @memoized
    def crud_manager(self):
        crud_manager = super(BaseIndicatorDefinitionForm, self).crud_manager
        crud_manager.domain = self.domain
        return crud_manager


class FormLabelIndicatorDefinitionForm(BaseIndicatorDefinitionForm):
    xmlns = forms.CharField(label="XMLNS")

    def clean_xmlns(self):
        if 'xmlns' in self.cleaned_data:
            return self.cleaned_data['xmlns'].strip()

    doc_class = FormLabelIndicatorDefinition


class FormDataAliasIndicatorDefinitionForm(FormLabelIndicatorDefinitionForm):
    question_id = forms.CharField(label="Question ID")

    doc_class = FormDataAliasIndicatorDefinition

    def clean_question_id(self):
        if 'question_id' in self.cleaned_data:
            return self.cleaned_data['question_id'].strip()


class CaseDataInFormIndicatorDefinitionForm(FormLabelIndicatorDefinitionForm):
    case_property = forms.CharField(label="Case Property")

    doc_class = CaseDataInFormIndicatorDefinition


class BaseCaseIndicatorDefinitionForm(BaseIndicatorDefinitionForm):
    case_type = forms.CharField(label="Case Type")

    def clean_case_type(self):
        if 'case_type' in self.cleaned_data:
            return self.cleaned_data['case_type'].strip()


class FormDataInCaseForm(BaseCaseIndicatorDefinitionForm):
    xmlns = forms.CharField(label="XMLNS of Related Form")
    question_id = forms.CharField(label="Question ID of Related Form")

    doc_class = FormDataInCaseIndicatorDefinition

    def clean_xmlns(self):
        if 'xmlns' in self.cleaned_data:
            return self.cleaned_data['xmlns'].strip()

    def clean_question_id(self):
        if 'question_id' in self.cleaned_data:
            return self.cleaned_data['question_id'].strip()


class BaseDynamicIndicatorForm(BaseIndicatorDefinitionForm):
    title = forms.CharField(label="Title", help_text="This should be the shortened version of the description.")
    description = forms.CharField(label="Description", help_text="The description of what this indicator means.")


class CouchIndicatorForm(BaseDynamicIndicatorForm):
    couch_view = forms.CharField(label="Couch View")
    indicator_key = forms.CharField(label="Indicator Key", required=False)
    #todo provide reasonable labels for these
    startdate_shift = forms.IntegerField(label="Start Date Shift", required=False)
    enddate_shift = forms.IntegerField(label="End Date Shift", required=False)
    fixed_datespan_days = forms.IntegerField(label="Fix Datespan by Days", required=False)
    fixed_datespan_months = forms.IntegerField(label="Fix Datespan by Months", required=False)

    doc_class = CouchIndicatorDef

    def clean_fixed_datespan_days(self):
        if 'fixed_datespan_days' in self.cleaned_data:
            return abs(self.cleaned_data['fixed_datespan_days'])

    def clean_fixed_datespan_months(self):
        if 'fixed_datespan_months' in self.cleaned_data:
            return abs(self.cleaned_data['fixed_datespan_months'])


class CountUniqueCouchIndicatorForm(CouchIndicatorForm):
    doc_class = CountUniqueCouchIndicatorDef


class MedianCouchIndicatorForm(CouchIndicatorForm):
    doc_class = MedianCouchIndicatorDef


class SumLastEmittedCouchIndicatorForm(CouchIndicatorForm):
    doc_class = SumLastEmittedCouchIndicatorDef


class CombinedIndicatorForm(BaseDynamicIndicatorForm):
    numerator_slug = forms.SlugField(label="Numerator Slug")
    denominator_slug = forms.SlugField(label="Denominator Slug")

    doc_class = CombinedCouchViewIndicatorDefinition

    @property
    def available_slugs(self):
        key = [self.cleaned_data['namespace'], self.domain]
        slugs = DynamicIndicatorDefinition.get_db().view("indicators/available_to_combine",
                                                         group=True,
                                                         group_level=3,
                                                         startkey=key,
                                                         endkey=key+[{}]
        ).all()
        return [s['key'][-1] for s in slugs]

    def _check_if_slug_exists(self, slug):
        if slug not in self.available_slugs:
            raise ValidationError("An indicator with slug %s does not exist. Please create this indicator first."
                                  % slug)
        return slug

    def clean_numerator_slug(self):
        if 'numerator_slug' in self.cleaned_data:
            return self._check_if_slug_exists(self.cleaned_data['numerator_slug'])

    def clean_denominator_slug(self):
        if 'denominator_slug' in self.cleaned_data:
            return self._check_if_slug_exists(self.cleaned_data['denominator_slug'])




