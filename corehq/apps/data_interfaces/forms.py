import json
import re

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from couchdbkit import ResourceNotFound
from crispy_forms.bootstrap import FieldWithButtons, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Div, Field, Fieldset, Layout
from memoized import memoized

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseRuleAction,
    CaseRuleCriteria,
    ClosedParentDefinition,
    CustomActionDefinition,
    CustomMatchDefinition,
    LocationFilterDefinition,
    MatchPropertyDefinition,
    UCRFilterDefinition,
    UpdateCaseDefinition,
)
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.hqwebapp.widgets import SelectToggle
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.toggles import CASE_UPDATES_UCR_FILTERS


def true_or_false(value):
    if value == 'true':
        return True
    elif value == 'false':
        return False

    raise ValueError("Expected 'true' or 'false'")


def remove_quotes(value):
    if isinstance(value, str) and len(value) >= 2:
        for q in ("'", '"'):
            if value.startswith(q) and value.endswith(q):
                return value[1:-1]
    return value


def is_valid_case_property_name(value):
    if not isinstance(value, str):
        return False
    try:
        validate_case_property_characters(value)
        return True
    except ValidationError:
        return False


def validate_case_property_characters(value):
    if not re.match('^[a-zA-Z0-9_-]+$', value):
        raise ValidationError(
            _("Property names should only contain alphanumeric characters, underscore, or hyphen.")
        )


def validate_case_property_name(value, allow_parent_case_references=True):
    if not isinstance(value, str):
        raise ValidationError(_("Please specify a case property name."))

    value = value.strip()

    if not value:
        raise ValidationError(_("Please specify a case property name."))

    if not allow_parent_case_references:
        if '/' in value:
            raise ValidationError(
                _("Invalid character '/' in case property name: '{}'. "
                  "Parent or host case references are not allowed.").format(value)
            )
        validate_case_property_characters(value)
    else:
        property_name = re.sub('^(parent/|host/)+', '', value)
        if not property_name:
            raise ValidationError(_("Please specify a case property name."))

        if '/' in property_name:
            raise ValidationError(
                _("Case property reference cannot contain '/' unless referencing the parent "
                  "or host case with 'parent/' or 'host/'")
            )

        validate_case_property_characters(property_name)

    return value


def hidden_bound_field(field_name, data_value):
    return Field(
        field_name,
        type='hidden',
        data_bind='value: %s' % data_value,
    )


def validate_case_property_value(value):
    if not isinstance(value, str):
        raise ValidationError(_("Please specify a case property value."))

    value = remove_quotes(value.strip()).strip()
    if not value:
        raise ValidationError(_("Please specify a case property value."))

    return value


def validate_non_negative_days(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(_("Please enter a number of days greater than or equal to zero"))

    if value < 0:
        raise ValidationError(_("Please enter a number of days greater than or equal to zero"))

    return value


class AddCaseGroupForm(forms.Form):
    name = forms.CharField(required=True, label=gettext_noop("Group Name"))

    def __init__(self, *args, **kwargs):
        super(AddCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField('name'),
            StrictButton(
                format_html('<i class="fa fa-plus"></i> {}', _("Add Group")),
                css_class='btn-primary',
                type="submit"
            )
        )

    def create_group(self, domain):
        group = CommCareCaseGroup(
            name=self.cleaned_data['name'],
            domain=domain
        )
        group.save()
        return group


class UpdateCaseGroupForm(AddCaseGroupForm):
    item_id = forms.CharField(widget=forms.HiddenInput())
    action = forms.CharField(widget=forms.HiddenInput(), initial="update_case_group")

    def __init__(self, *args, **kwargs):
        super(UpdateCaseGroupForm, self).__init__(*args, **kwargs)

        self.fields['name'].label = ""

        self.helper.form_style = 'inline'
        self.helper.form_method = 'post'
        self.helper.form_show_labels = True
        self.helper.layout = Layout(
            'item_id',
            'action',
            FieldWithButtons(
                Field('name', placeholder="Group Name"),
                StrictButton(
                    _("Update Group Name"),
                    css_class='btn-primary',
                    type="submit",
                )
            ),
        )

    def clean(self):
        cleaned_data = super(UpdateCaseGroupForm, self).clean()
        try:
            self.current_group = CommCareCaseGroup.get(self.cleaned_data.get('item_id'))
        except AttributeError:
            raise forms.ValidationError(_("Please include the case group ID."))
        except ResourceNotFound:
            raise forms.ValidationError(_("A case group was not found with that ID."))
        return cleaned_data

    def update_group(self):
        self.current_group.name = self.cleaned_data['name']
        self.current_group.save()
        return self.current_group


class AddCaseToGroupForm(forms.Form):
    case_identifier = forms.CharField(label=gettext_noop("Case ID, External ID, or Phone Number"))

    def __init__(self, *args, **kwargs):
        super(AddCaseToGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField(
                'case_identifier'
            ),
            StrictButton(
                format_html('<i class="fa fa-plus"></i> {}', _("Add Case")),
                css_class='btn-primary',
                type="submit"
            )
        )


class CaseUpdateRuleForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "rule-"
    prefix = "rule"

    name = TrimmedCharField(
        label=gettext_lazy("Name"),
        required=True,
    )

    def compute_initial(self, domain, rule):
        return {
            'name': rule.name,
        }

    def __init__(self, domain, *args, **kwargs):
        if 'initial' in kwargs:
            raise ValueError(_("Initial values are set by the form"))

        self.is_system_admin = kwargs.pop('is_system_admin', False)

        rule = kwargs.pop('rule', None)
        if rule:
            kwargs['initial'] = self.compute_initial(domain, rule)

        super(CaseUpdateRuleForm, self).__init__(*args, **kwargs)

        self.domain = domain
        self.helper = HQFormHelper()
        self.helper.form_tag = False

        self.helper.layout = Layout(
            Fieldset(
                _("Basic Information"),
                Field('name', data_bind='name'),
            ),
        )


class CaseRuleCriteriaForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "criteria-"
    prefix = "criteria"

    case_type = forms.ChoiceField(
        label=gettext_lazy("Case Type"),
        required=True,
    )
    criteria_operator = forms.ChoiceField(
        label=gettext_lazy("Run when"),
        required=False,
        initial='ALL',
        choices=AutomaticUpdateRule.CriteriaOperator.choices,
        widget=SelectToggle(
            choices=AutomaticUpdateRule.CriteriaOperator.choices,
            attrs={"ko_value": "criteriaOperator"}
        ),
    )

    filter_on_server_modified = forms.CharField(required=False, initial='false')
    server_modified_boundary = forms.CharField(required=False, initial='')
    custom_match_definitions = forms.CharField(required=False, initial='[]')
    property_match_definitions = forms.CharField(required=False, initial='[]')
    filter_on_closed_parent = forms.CharField(required=False, initial='false')
    location_filter_definition = forms.CharField(required=False, initial='')
    ucr_filter_definitions = forms.JSONField(required=False, initial=list)

    @property
    def current_values(self):
        return {
            'filter_on_server_modified': self['filter_on_server_modified'].value(),
            'server_modified_boundary': self['server_modified_boundary'].value(),
            'custom_match_definitions': json.loads(self['custom_match_definitions'].value()),
            'property_match_definitions': json.loads(self['property_match_definitions'].value()),
            'filter_on_closed_parent': self['filter_on_closed_parent'].value(),
            'case_type': self['case_type'].value(),
            'location_filter_definition': self['location_filter_definition'].value(),
            'criteria_operator': self['criteria_operator'].value(),
            'ucr_filter_definitions': json.loads(self['ucr_filter_definitions'].value()),
        }

    @property
    def constants(self):
        return {
            'MATCH_DAYS_BEFORE': MatchPropertyDefinition.MATCH_DAYS_BEFORE,
            'MATCH_DAYS_AFTER': MatchPropertyDefinition.MATCH_DAYS_AFTER,
            'MATCH_EQUAL': MatchPropertyDefinition.MATCH_EQUAL,
            'MATCH_NOT_EQUAL': MatchPropertyDefinition.MATCH_NOT_EQUAL,
            'MATCH_HAS_VALUE': MatchPropertyDefinition.MATCH_HAS_VALUE,
            'MATCH_HAS_NO_VALUE': MatchPropertyDefinition.MATCH_HAS_NO_VALUE,
            'MATCH_REGEX': MatchPropertyDefinition.MATCH_REGEX,
        }

    def compute_initial(self, domain, rule):
        initial = {
            'case_type': rule.case_type,
            'criteria_operator': rule.criteria_operator,
            'filter_on_server_modified': 'true' if rule.filter_on_server_modified else 'false',
            'server_modified_boundary': rule.server_modified_boundary,
        }

        custom_match_definitions = []
        property_match_definitions = []
        ucr_filter_definitions = []

        for criteria in rule.memoized_criteria:
            definition = criteria.definition
            if isinstance(definition, MatchPropertyDefinition):
                property_match_definitions.append({
                    'property_name': definition.property_name,
                    'property_value': definition.property_value,
                    'match_type': definition.match_type,
                })
            elif isinstance(definition, CustomMatchDefinition):
                custom_match_definitions.append({
                    'name': definition.name,
                })
            elif isinstance(definition, ClosedParentDefinition):
                initial['filter_on_closed_parent'] = 'true'
            elif isinstance(definition, LocationFilterDefinition):
                location_id = definition.location_id
                location = SQLLocation.by_location_id(location_id)

                initial['location_filter_definition'] = {
                    'location_id': location_id,
                    'include_child_locations': definition.include_child_locations,
                    'name': location.name,
                }
            elif isinstance(definition, UCRFilterDefinition):
                ucr_filter_definitions.append({
                    'configured_filter': definition.configured_filter,
                })

        initial['custom_match_definitions'] = json.dumps(custom_match_definitions)
        initial['property_match_definitions'] = json.dumps(property_match_definitions)
        initial['ucr_filter_definitions'] = ucr_filter_definitions

        return initial

    @property
    def show_fieldset_title(self):
        return True

    @property
    def fieldset_help_text(self):
        return _("The Actions will be performed for all open cases that match all filter criteria below.")

    @property
    def allow_parent_case_references(self):
        return True

    @property
    def allow_case_modified_filter(self):
        return True

    @property
    def allow_case_property_filter(self):
        return True

    @property
    def allow_date_case_property_filter(self):
        return True

    @property
    def allow_ucr_filter(self):
        return CASE_UPDATES_UCR_FILTERS.enabled(self.domain)

    @property
    def allow_regex_case_property_match(self):
        # The framework allows for this, it's just historically only
        # been an option for messaging conditonal alert rules and not
        # case update rules. So for now the option is just hidden in
        # the case update rule UI.
        return False

    @property
    def allow_locations_filter(self):
        return False

    @property
    def allow_custom_filter(self):
        return True

    def __init__(self, domain, *args, **kwargs):
        if 'initial' in kwargs:
            raise ValueError(_("Initial values are set by the form."))

        self.is_system_admin = kwargs.pop('is_system_admin', False)
        self.couch_user = kwargs.pop('couch_user', None)
        self.domain = domain

        self.initial_rule = kwargs.pop('rule', None)
        if self.initial_rule:
            kwargs['initial'] = self.compute_initial(domain, self.initial_rule)

        super(CaseRuleCriteriaForm, self).__init__(*args, **kwargs)

        self.set_case_type_choices(self.initial.get('case_type'))
        self.fields['criteria_operator'].choices = AutomaticUpdateRule.CriteriaOperator.choices

        self.helper = HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                _("Case Filters") if self.show_fieldset_title else "",
                HTML(
                    '<p class="help-block alert alert-info"><i class="fa fa-info-circle"></i> %s</p>'
                    % self.fieldset_help_text
                ),
                hidden_bound_field('filter_on_server_modified', 'filterOnServerModified'),
                hidden_bound_field('server_modified_boundary', 'serverModifiedBoundary'),
                hidden_bound_field('custom_match_definitions', 'customMatchDefinitions'),
                hidden_bound_field('property_match_definitions', 'propertyMatchDefinitions'),
                hidden_bound_field('filter_on_closed_parent', 'filterOnClosedParent'),
                hidden_bound_field('location_filter_definition', 'locationFilterDefinition'),
                hidden_bound_field('ucr_filter_definitions', 'ucrFilterDefinitions'),
                Div(data_bind="template: {name: 'case-filters'}"),
                css_id="rule-criteria-panel",
            ),
        )

        self.form_beginning_helper = HQFormHelper()
        self.form_beginning_helper.form_tag = False
        self.form_beginning_helper.layout = Layout(
            Fieldset(
                _("Rule Criteria"),
                Field('case_type', data_bind="value: caseType, staticSelect2: {}"),
                Field('criteria_operator'),
            )
        )

        self.custom_filters = settings.AVAILABLE_CUSTOM_RULE_CRITERIA.keys()

    def user_locations(self):
        if self.couch_user:
            user_locations = SQLLocation.objects.accessible_to_user(self.domain, self.couch_user)
            return [
                {'location_id': location.location_id, 'name': location.name}
                for location in user_locations
            ]
        return []

    @property
    @memoized
    def requires_system_admin_to_edit(self):
        if 'custom_match_definitions' not in self.initial:
            return False

        custom_criteria = json.loads(self.initial['custom_match_definitions'])
        return len(custom_criteria) > 0

    @property
    @memoized
    def requires_system_admin_to_save(self):
        return len(self.cleaned_data['custom_match_definitions']) > 0

    def _json_fail_hard(self):
        raise ValueError(_("Invalid JSON object given"))

    def set_case_type_choices(self, initial):
        case_types = [''] + list(get_case_types_for_domain(self.domain))
        if initial and initial not in case_types:
            # Include the deleted case type in the list of choices so that
            # we always allow proper display and edit of rules
            case_types.append(initial)
        case_types.sort()
        self.fields['case_type'].choices = (
            (case_type, case_type) for case_type in case_types
        )

    def clean_filter_on_server_modified(self):
        return true_or_false(self.cleaned_data.get('filter_on_server_modified'))

    def clean_server_modified_boundary(self):
        # Be explicit about this check to prevent any accidents in the future
        if self.cleaned_data['filter_on_server_modified'] is False:
            return None

        value = self.cleaned_data.get('server_modified_boundary')
        return validate_non_negative_days(value)

    def clean_custom_match_definitions(self):
        value = self.cleaned_data.get('custom_match_definitions')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if 'name' not in obj:
                self._json_fail_hard()

            name = obj['name'].strip()

            result.append({
                'name': name
            })

        return result

    def clean_property_match_definitions(self):
        value = self.cleaned_data.get('property_match_definitions')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if (
                'property_name' not in obj
                or 'property_value' not in obj
                or 'match_type' not in obj
            ):
                self._json_fail_hard()

            property_name = validate_case_property_name(obj['property_name'],
                allow_parent_case_references=self.allow_parent_case_references)
            match_type = obj['match_type']
            if match_type not in MatchPropertyDefinition.MATCH_CHOICES:
                self._json_fail_hard()

            if match_type in (
                MatchPropertyDefinition.MATCH_HAS_VALUE,
                MatchPropertyDefinition.MATCH_HAS_NO_VALUE,
            ):
                result.append({
                    'property_name': property_name,
                    'property_value': None,
                    'match_type': match_type,
                })
            elif match_type in (
                MatchPropertyDefinition.MATCH_EQUAL,
                MatchPropertyDefinition.MATCH_NOT_EQUAL,
            ):
                property_value = validate_case_property_value(obj['property_value'])
                result.append({
                    'property_name': property_name,
                    'property_value': property_value,
                    'match_type': match_type,
                })
            elif match_type in (
                MatchPropertyDefinition.MATCH_DAYS_BEFORE,
                MatchPropertyDefinition.MATCH_DAYS_AFTER,
            ):
                property_value = obj['property_value']
                try:
                    property_value = int(property_value)
                except (TypeError, ValueError):
                    raise ValidationError(_("Please enter a number of days"))

                result.append({
                    'property_name': property_name,
                    'property_value': str(property_value),
                    'match_type': match_type,
                })
            elif match_type == MatchPropertyDefinition.MATCH_REGEX:
                property_value = obj['property_value']

                if not property_value:
                    raise ValidationError(_("Please enter a valid regular expression to match"))

                try:
                    re.compile(property_value)
                except (re.error, ValueError, TypeError):
                    raise ValidationError(_("Please enter a valid regular expression to match"))

                result.append({
                    'property_name': property_name,
                    'property_value': property_value,
                    'match_type': match_type,
                })
        return result

    def clean_filter_on_closed_parent(self):
        return true_or_false(self.cleaned_data.get('filter_on_closed_parent'))

    def clean_location_filter_definition(self):
        value = self.cleaned_data.get('location_filter_definition')
        try:
            if value:
                value = json.loads(value)
            else:
                return ''
        except (TypeError, ValueError):
            self._json_fail_hard()

        if value:
            if not value.get('include_child_locations'):
                value['include_child_locations'] = False
            return value
        return ''

    def clean_ucr_filter_definitions(self):
        value = self.cleaned_data.get('ucr_filter_definitions')

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()
            try:
                spec = json.loads(obj['configured_filter'])
            except (TypeError, ValueError):
                self._json_fail_hard()

            try:
                FilterFactory.from_spec(spec, FactoryContext.empty(domain=self.domain))
            except BadSpecError as error:
                message = _("There was a problem with a UCR Filter Definition: ")
                raise ValidationError(message + str(error))

            result.append(obj)

        return result

    def save_criteria(self, rule, save_meta=True):
        with transaction.atomic():
            if save_meta:
                rule.case_type = self.cleaned_data['case_type']
                rule.criteria_operator = self.cleaned_data['criteria_operator']
                rule.filter_on_server_modified = self.cleaned_data['filter_on_server_modified']
                rule.server_modified_boundary = self.cleaned_data['server_modified_boundary']
                rule.save()

            rule.delete_criteria()

            for item in self.cleaned_data['property_match_definitions']:
                definition = MatchPropertyDefinition.objects.create(
                    property_name=item['property_name'],
                    property_value=item['property_value'],
                    match_type=item['match_type'],
                )

                criteria = CaseRuleCriteria(rule=rule)
                criteria.definition = definition
                criteria.save()

            for item in self.cleaned_data['custom_match_definitions']:
                definition = CustomMatchDefinition.objects.create(
                    name=item['name'],
                )

                criteria = CaseRuleCriteria(rule=rule)
                criteria.definition = definition
                criteria.save()

            for item in self.cleaned_data['ucr_filter_definitions']:
                definition = UCRFilterDefinition.objects.create(
                    configured_filter=item['configured_filter']
                )
                criteria = CaseRuleCriteria(rule=rule)
                criteria.definition = definition
                criteria.save()

            if self.cleaned_data['filter_on_closed_parent']:
                definition = ClosedParentDefinition.objects.create()

                criteria = CaseRuleCriteria(rule=rule)
                criteria.definition = definition
                criteria.save()

            if self.cleaned_data['location_filter_definition']:
                definition_data = self.cleaned_data['location_filter_definition']

                if definition_data and definition_data['location_id']:
                    definition = LocationFilterDefinition.objects.create(
                        location_id=definition_data['location_id'],
                        include_child_locations=definition_data.get('include_child_locations', False),
                    )

                    criteria = CaseRuleCriteria(rule=rule)
                    criteria.definition = definition
                    criteria.save()


class CaseRuleActionsForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "action-"
    prefix = "action"

    close_case = forms.CharField(required=False, initial='false')
    properties_to_update = forms.CharField(required=False, initial='[]')
    custom_action_definitions = forms.CharField(required=False, initial='[]')

    @property
    def current_values(self):
        return {
            'close_case': self['close_case'].value(),
            'properties_to_update': json.loads(self['properties_to_update'].value()),
            'custom_action_definitions': json.loads(self['custom_action_definitions'].value()),
        }

    def compute_initial(self, domain, rule):
        initial = {}
        custom_action_definitions = []

        for action in rule.memoized_actions:
            definition = action.definition
            if isinstance(definition, UpdateCaseDefinition):
                if definition.close_case:
                    initial['close_case'] = 'true'
                initial['properties_to_update'] = json.dumps(definition.properties_to_update)
            elif isinstance(definition, CustomActionDefinition):
                custom_action_definitions.append({
                    'name': definition.name,
                })

        initial['custom_action_definitions'] = json.dumps(custom_action_definitions)
        return initial

    def __init__(self, domain, *args, **kwargs):
        if 'initial' in kwargs:
            raise ValueError(_("Initial values are set by the form."))

        self.is_system_admin = kwargs.pop('is_system_admin', False)

        rule = kwargs.pop('rule', None)
        if rule:
            kwargs['initial'] = self.compute_initial(domain, rule)

        super(CaseRuleActionsForm, self).__init__(*args, **kwargs)

        self.domain = domain

        self.helper = HQFormHelper()
        self.helper.form_tag = False
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            Fieldset(
                _("Actions"),
                hidden_bound_field('close_case', 'closeCase'),
                hidden_bound_field('properties_to_update', 'propertiesToUpdate'),
                hidden_bound_field('custom_action_definitions', 'customActionDefinitions'),
                Div(data_bind="template: {name: 'case-actions'}"),
                css_id="rule-actions",
            ),
        )

        self.custom_actions = settings.AVAILABLE_CUSTOM_RULE_ACTIONS.keys()

    @property
    def constants(self):
        return {
            'VALUE_TYPE_EXACT': UpdateCaseDefinition.VALUE_TYPE_EXACT,
            'VALUE_TYPE_CASE_PROPERTY': UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY,
        }

    @property
    @memoized
    def requires_system_admin_to_edit(self):
        if 'custom_action_definitions' not in self.initial:
            return False

        custom_actions = json.loads(self.initial['custom_action_definitions'])
        return len(custom_actions) > 0

    @property
    @memoized
    def requires_system_admin_to_save(self):
        return len(self.cleaned_data['custom_action_definitions']) > 0

    def _json_fail_hard(self):
        raise ValueError("Invalid JSON object given")

    def clean_close_case(self):
        return true_or_false(self.cleaned_data.get('close_case'))

    def clean_properties_to_update(self):
        value = self.cleaned_data.get('properties_to_update')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if (
                'name' not in obj
                or 'value_type' not in obj
                or 'value' not in obj
            ):
                self._json_fail_hard()

            name = validate_case_property_name(obj['name'])
            value_type = obj['value_type']
            if value_type not in UpdateCaseDefinition.VALUE_TYPE_CHOICES:
                self._json_fail_hard()

            if value_type == UpdateCaseDefinition.VALUE_TYPE_EXACT:
                value = validate_case_property_value(obj['value'])
            elif value_type == UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY:
                value = validate_case_property_name(obj['value'])

            result.append(
                UpdateCaseDefinition.PropertyDefinition(
                    name=name,
                    value_type=value_type,
                    value=value,
                )
            )

        return result

    def clean_custom_action_definitions(self):
        value = self.cleaned_data.get('custom_action_definitions')
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            self._json_fail_hard()

        if not isinstance(value, list):
            self._json_fail_hard()

        result = []

        for obj in value:
            if not isinstance(obj, dict):
                self._json_fail_hard()

            if 'name' not in obj:
                self._json_fail_hard()

            name = obj['name'].strip()

            result.append({
                'name': name
            })

        return result

    def clean(self):
        cleaned_data = super(CaseRuleActionsForm, self).clean()
        if (
            'close_case' in cleaned_data
            and 'properties_to_update' in cleaned_data
            and 'custom_action_definitions' in cleaned_data
        ):
            # All fields passed individual validation
            if (
                not cleaned_data['close_case']
                and not cleaned_data['properties_to_update']
                and not cleaned_data['custom_action_definitions']
            ):
                raise ValidationError(_("Please specify at least one action."))

    def save_actions(self, rule):
        with transaction.atomic():
            rule.delete_actions()

            if self.cleaned_data['close_case'] or self.cleaned_data['properties_to_update']:
                definition = UpdateCaseDefinition(close_case=self.cleaned_data['close_case'])
                definition.set_properties_to_update(self.cleaned_data['properties_to_update'])
                definition.save()

                action = CaseRuleAction(rule=rule)
                action.definition = definition
                action.save()

            for item in self.cleaned_data['custom_action_definitions']:
                definition = CustomActionDefinition.objects.create(
                    name=item['name'],
                )

                action = CaseRuleAction(rule=rule)
                action.definition = definition
                action.save()


class DedupeCaseFilterForm(CaseRuleCriteriaForm):

    prefix = 'case-filter'

    case_type = forms.ChoiceField(
        label=gettext_lazy("Case Type"),
        required=False,
    )

    @property
    def fieldset_help_text(self):
        return _("The rule will be applied to all cases that match all filter criteria below.")

    @property
    def allow_case_modified_filter(self):
        return False

    @property
    def allow_case_property_filter(self):
        return True

    @property
    def allow_date_case_property_filter(self):
        return False

    @property
    def allow_locations_filter(self):
        return True

    @property
    def allow_parent_case_references(self):
        return False

    @property
    def allow_custom_filter(self):
        return False

    def __init__(self, domain, *args, **kwargs):
        couch_user = kwargs.get('couch_user', None)
        kwargs['is_system_admin'] = couch_user.is_superuser if couch_user else False
        super(DedupeCaseFilterForm, self).__init__(domain, *args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                _("Cases Filter") if self.show_fieldset_title else "",
                HTML(
                    '<p class="help-block alert alert-info"><i class="fa fa-info-circle"></i> %s</p>'
                    % self.fieldset_help_text
                ),
                hidden_bound_field('property_match_definitions', 'propertyMatchDefinitions'),
                hidden_bound_field('location_filter_definition', 'locationFilterDefinition'),
                Div(data_bind="template: {name: 'case-filters'}"),
                css_id="rule-criteria-panel",
            ),
        )
        self.form_beginning_helper = None

    def clean_filter_on_server_modified(self):
        return False

    def clean_server_modified_boundary(self):
        return None

    def clean_custom_match_definitions(self):
        return []

    def clean_filter_on_closed_parent(self):
        return False

    def clean_ucr_filter_definitions(self):
        return []
