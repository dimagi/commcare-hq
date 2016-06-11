from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.forms import MultipleChoiceField
from django.forms.utils import ErrorList
from corehq.apps.crud.models import BaseAdminCRUDForm
from corehq.apps.indicators.models import (
    FormDataAliasIndicatorDefinition,
    FormLabelIndicatorDefinition,
    CaseDataInFormIndicatorDefinition,
    FormDataInCaseIndicatorDefinition,
    CouchIndicatorDef,
    CountUniqueCouchIndicatorDef,
    MedianCouchIndicatorDef,
    CombinedCouchViewIndicatorDefinition,
    SumLastEmittedCouchIndicatorDef,
    DynamicIndicatorDefinition,
)
from corehq.apps.indicators.utils import get_namespaces, get_namespace_name, get_indicator_domains
from corehq.apps.users.models import Permissions
from crispy_forms.helper import FormHelper
from dimagi.utils.decorators.memoized import memoized


class BaseIndicatorDefinitionForm(BaseAdminCRUDForm):
    slug = forms.SlugField(label="Slug")
    namespace = forms.CharField(label="Namespace", widget=forms.Select(choices=[]))

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, doc_id=None, domain=None):
        super(BaseIndicatorDefinitionForm, self).__init__(data, files, auto_id, prefix, initial, error_class,
                                                          label_suffix, empty_permitted, doc_id)
        self.domain = domain
        self.fields['namespace'].widget = forms.Select(choices=get_namespaces(self.domain, as_choices=True))
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-9'

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

    change_doc_type = forms.BooleanField(label="Change Indicator Type?", required=False, initial=False)
    doc_type_choices = forms.CharField(label="Choose Indicator Type", required=False, widget=forms.Select(choices=[]))

    doc_class = CouchIndicatorDef

    def __init__(self, *args, **kwargs):
        super(CouchIndicatorForm, self).__init__(*args, **kwargs)
        if self.existing_object:
            self.fields['doc_type_choices'].widget.choices = [(d.__name__, d.get_nice_name())
                                                              for d in self.available_doc_types]
        else:
            del self.fields['change_doc_type']
            del self.fields['doc_type_choices']

    @property
    def available_doc_types(self):
        subclasses = set([CouchIndicatorDef, CountUniqueCouchIndicatorDef,
                      MedianCouchIndicatorDef, SumLastEmittedCouchIndicatorDef])
        return subclasses.difference([self.doc_class])

    def clean_fixed_datespan_days(self):
        if 'fixed_datespan_days' in self.cleaned_data and self.cleaned_data['fixed_datespan_days']:
            return abs(self.cleaned_data['fixed_datespan_days'])

    def clean_fixed_datespan_months(self):
        if 'fixed_datespan_months' in self.cleaned_data and self.cleaned_data['fixed_datespan_months']:
            return abs(self.cleaned_data['fixed_datespan_months'])

    def clean_doc_type_choices(self):
        if ('doc_type_choices' in self.cleaned_data
            and 'change_doc_type' in self.cleaned_data
            and self.cleaned_data['change_doc_type']):
            subclass_to_class = dict([(d.__name__, d) for d in self.available_doc_types])
            if self.existing_object:
                self.existing_object.doc_type = self.cleaned_data['doc_type_choices']
                self.existing_object.save()
            return self.cleaned_data['doc_type_choices']


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


class BulkCopyIndicatorsForm(forms.Form):
    destination_domain = forms.CharField(label="Destination Project Space")
    indicator_ids = MultipleChoiceField(
        label="Indicator(s)",
        validators=[MinLengthValidator(1)])

    def __init__(self, domain=None, couch_user=None, indicator_class=None, *args, **kwargs):
        super(BulkCopyIndicatorsForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.couch_user = couch_user
        self.indicator_class = indicator_class

        self.fields['destination_domain'].widget = forms.Select(choices=[(d, d) for d in self.available_domains])
        self.fields['indicator_ids'].choices = self.available_indicators

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3'
        self.helper.field_class = 'col-sm-9'

    @property
    @memoized
    def available_domains(self):
        if not self.couch_user:
            return []
        indicator_domains = set(get_indicator_domains())
        indicator_domains = indicator_domains.difference([self.domain])
        return [d for d in indicator_domains if self.couch_user.has_permission(d, Permissions.edit_data)]

    @property
    @memoized
    def available_indicators(self):
        indicators = []
        for namespace in get_namespaces(self.domain):
            indicators.extend(self.indicator_class.get_all_of_type(namespace, self.domain))
        return [(i._id, "%s | v. %d | n: %s" % (i.slug, i.version if i.version else 0,
                                                get_namespace_name(i.domain, i.namespace))) for i in indicators]

    def clean_destination_domain(self):
        if 'destination_domain' in self.cleaned_data:
            destination = self.cleaned_data['destination_domain']
            if not self.couch_user or not self.couch_user.has_permission(destination, Permissions.edit_data):
                raise ValidationError("You do not have permission to copy indicators to this project space.")
            if destination not in self.available_domains:
                raise ValidationError("You submitted an invalid destination project space")
            return destination

    def copy_indicators(self):
        failed = []
        success = []
        destination_domain = self.cleaned_data['destination_domain']
        available_namespaces = get_namespaces(destination_domain)
        indicator_ids = self.cleaned_data['indicator_ids']
        for indicator_id in indicator_ids:
            try:
                indicator = self.indicator_class.get(indicator_id)
                properties_to_exclude = [
                    'last_modified',
                    'base_doc',
                    'namespace',
                    'domain',
                    'class_path',
                    'version'
                ]
                if indicator.namespace not in available_namespaces:
                    failed.append(dict(indicator=indicator.slug,
                                       reason='Indicator namespace not available for destination project.'))
                    continue

                properties = set(indicator.properties().keys())
                copied_properties = properties.difference(properties_to_exclude)
                copied_properties = dict([(p, getattr(indicator, p)) for p in copied_properties])

                copied_indicator = self.indicator_class.increment_or_create_unique(
                    indicator.namespace,
                    destination_domain,
                    **copied_properties
                )
                if copied_indicator:
                    success.append(copied_indicator.slug)

            except Exception as e:
                failed.append(dict(indicator=indicator_id,
                                   reason='Could not retrieve indicator %s due to error %s:' % (indicator_id, e)))
        return {
            'success': success,
            'failure': failed,
        }
