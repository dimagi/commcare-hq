from __future__ import absolute_import
from __future__ import unicode_literals
import json
import re
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRuleCriteria,
    AutomaticUpdateAction,
    CaseRuleCriteria,
    MatchPropertyDefinition,
    ClosedParentDefinition,
    CustomMatchDefinition,
    CaseRuleAction,
    UpdateCaseDefinition,
    CustomActionDefinition,
)
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.apps.hqwebapp import crispy as hqcrispy
from couchdbkit import ResourceNotFound

from corehq.toggles import AUTO_CASE_UPDATE_ENHANCEMENTS
from crispy_forms.bootstrap import StrictButton, InlineField, FormActions, FieldWithButtons
from memoized import memoized
from django.db import transaction
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML, Div, Fieldset
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.casegroups.models import CommCareCaseGroup
from dimagi.utils.django.fields import TrimmedCharField
import six


def true_or_false(value):
    if value == 'true':
        return True
    elif value == 'false':
        return False

    raise ValueError("Expected 'true' or 'false'")


def remove_quotes(value):
    if isinstance(value, six.string_types) and len(value) >= 2:
        for q in ("'", '"'):
            if value.startswith(q) and value.endswith(q):
                return value[1:-1]
    return value


def validate_case_property_characters(value):
    if not re.match('^[a-zA-Z0-9_-]+$', value):
        raise ValidationError(
            _("Property names should only contain alphanumeric characters, underscore, or hyphen.")
        )


def validate_case_property_name(value, allow_parent_case_references=True):
    if not isinstance(value, six.string_types):
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


def hidden_bound_field(field_name):
    return Field(
        field_name,
        type='hidden',
        data_bind='value: %s' % field_name,
    )


def validate_case_property_value(value):
    if not isinstance(value, six.string_types):
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
    name = forms.CharField(required=True, label=ugettext_noop("Group Name"))

    def __init__(self, *args, **kwargs):
        super(AddCaseGroupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_style = 'inline'
        self.helper.form_show_labels = False
        self.helper.layout = Layout(
            InlineField('name'),
            StrictButton(
                mark_safe('<i class="fa fa-plus"></i> %s' % _("Create Group")),
                css_class='btn-success',
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
            raise forms.ValidationError("You're not passing in the group's id!")
        except ResourceNotFound:
            raise forms.ValidationError("This case group was not found in our database!")
        return cleaned_data

    def update_group(self):
        self.current_group.name = self.cleaned_data['name']
        self.current_group.save()
        return self.current_group


class AddCaseToGroupForm(forms.Form):
    case_identifier = forms.CharField(label=ugettext_noop("Case ID, External ID, or Phone Number"))

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
                mark_safe('<i class="fa fa-plus"></i> %s' % _("Add Case")),
                css_class='btn-success',
                type="submit"
            )
        )


class AddAutomaticCaseUpdateRuleForm(forms.Form):
    ACTION_CLOSE = 'CLOSE'
    ACTION_UPDATE_AND_CLOSE = 'UPDATE_AND_CLOSE'
    ACTION_UPDATE = 'UPDATE'

    name = TrimmedCharField(
        label=ugettext_lazy("Rule Name"),
        required=True,
    )
    case_type = forms.ChoiceField(
        label=ugettext_lazy("Case Type"),
        required=True,
    )
    filter_on_server_modified = forms.ChoiceField(
        label=ugettext_lazy("Filter on Last Modified"),
        choices=(
            ('true', ugettext_lazy("Yes")),
            ('false', ugettext_lazy("No")),
        ),
        required=False
    )
    server_modified_boundary = forms.IntegerField(
        label=ugettext_lazy("enter number of days"),
        required=False,
    )
    conditions = forms.CharField(
        required=True,
    )
    action = forms.ChoiceField(
        label=ugettext_lazy("Set a Case Property"),
        choices=(
            (ACTION_UPDATE_AND_CLOSE,
                ugettext_lazy("Yes")),
            (ACTION_CLOSE,
                ugettext_lazy("No")),
        ),
    )
    update_property_name = TrimmedCharField(
        required=False,
    )
    property_value_type = forms.ChoiceField(
        label=ugettext_lazy('Value Type'),
        choices=AutomaticUpdateAction.PROPERTY_TYPE_CHOICES,
        required=False
    )
    update_property_value = TrimmedCharField(
        required=False,
    )

    def remove_quotes(self, value):
        if isinstance(value, six.string_types) and len(value) >= 2:
            for q in ("'", '"'):
                if value.startswith(q) and value.endswith(q):
                    return value[1:-1]
        return value

    @property
    def current_values(self):
        values = {}
        for field_name in self.fields.keys():
            value = self[field_name].value()
            if field_name == 'conditions':
                value = value or '[]'
                value = json.loads(value)
            values[field_name] = value
        return values

    def set_case_type_choices(self, initial):
        case_types = [''] + list(get_case_types_for_domain_es(self.domain))
        if initial and initial not in case_types:
            # Include the deleted case type in the list of choices so that
            # we always allow proper display and edit of rules
            case_types.append(initial)
        case_types.sort()
        self.fields['case_type'].choices = (
            (case_type, case_type) for case_type in case_types
        )

    def allow_updates_without_closing(self):
        """
        If the AUTO_CASE_UPDATE_ENHANCEMENTS toggle is enabled for the domain, then
        we allow updates to happen without closing the case.
        """
        self.fields['action'].choices = (
            (self.ACTION_CLOSE, _("No")),
            (self.ACTION_UPDATE_AND_CLOSE, _("Yes, and close the case")),
            (self.ACTION_UPDATE, _("Yes, and do not close the case")),
        )

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception("Expected domain in kwargs")
        self.domain = kwargs.pop('domain')
        self.enhancements_enabled = AUTO_CASE_UPDATE_ENHANCEMENTS.enabled(self.domain)
        super(AddAutomaticCaseUpdateRuleForm, self).__init__(*args, **kwargs)

        if not self.enhancements_enabled:
            # Always set the value of filter_on_server_modified to true when the
            # enhancement toggle is not set
            self.data = self.data.copy()
            self.initial['filter_on_server_modified'] = 'true'
            self.data['filter_on_server_modified'] = 'true'

        # We can't set these fields to be required because they are displayed
        # conditionally and we'll confuse django validation if we make them
        # required. However, we should show the asterisk for consistency, since
        # when they are displayed they are required.
        self.fields['update_property_name'].label = _("Property") + '<span class="asteriskField">*</span>'
        self.fields['update_property_value'].label = _("Value") + '<span class="asteriskField">*</span>'
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        if self.enhancements_enabled:
            self.allow_updates_without_closing()

        _update_property_fields = [_f for _f in [
            Field(
                'update_property_name',
                ng_model='update_property_name',
                css_class='case-property-typeahead',
            ),
            Field(
                'property_value_type',
                ng_model='property_value_type',
            ) if self.enhancements_enabled else None,
            Field(
                'update_property_value',
                ng_model='update_property_value',
            )
        ] if _f]

        _basic_info_fields = [_f for _f in [
            Field(
                'name',
                ng_model='name',
            ),
            Field(
                'case_type',
                ng_model='case_type',
            ),
            Field(
                'filter_on_server_modified',
                ng_model='filter_on_server_modified',
            ) if self.enhancements_enabled else None,
            hqcrispy.B3MultiField(
                _("Close Case") + '<span class="asteriskField">*</span>',
                Div(
                    hqcrispy.MultiInlineField(
                        'server_modified_boundary',
                        ng_model='server_modified_boundary',
                    ),
                    css_class='col-sm-6',
                ),
                Div(
                    HTML('<label class="control-label">%s</label>' %
                         _('days after the case was last modified.')),
                    css_class='col-sm-6',
                ),
                help_bubble_text=_("This will close the case if it has been "
                                   "more than the chosen number of days since "
                                   "the case was last modified. Cases are "
                                   "checked against this rule weekly."),
                css_id='server_modified_boundary_multifield',
                label_class=self.helper.label_class,
                field_class='col-sm-8 col-md-6',
                ng_show='showServerModifiedBoundaryField()',
            ),
            Field(
                'action',
                ng_model='action',
            ),
            Div(
                *_update_property_fields,
                ng_show='showUpdateProperty()'
            )
        ] if _f]

        self.set_case_type_choices(self.initial.get('case_type'))
        self.helper.layout = Layout(
            Fieldset(
                _("Basic Information"),
                *_basic_info_fields
            ),
            Fieldset(
                _("Filter Cases to Close (Optional)"),
                Field(
                    'conditions',
                    type='hidden',
                    ng_value='conditions',
                ),
                Div(ng_include='', src="'conditions.tpl'"),
            ),
            FormActions(
                StrictButton(
                    _("Save"),
                    type='submit',
                    css_class='btn btn-primary col-sm-offset-1',
                ),
            ),
        )

    def clean_server_modified_boundary(self):
        value = self.cleaned_data.get('server_modified_boundary')

        if self.enhancements_enabled:
            if not self.cleaned_data.get('filter_on_server_modified'):
                return None

            if not isinstance(value, int) or value <= 0:
                raise ValidationError(_("Please enter a whole number greater than 0."))
        else:
            if not isinstance(value, int) or value < 30:
                raise ValidationError(_("Please enter a whole number greater than or equal to 30."))

        return value

    def _clean_case_property_name(self, value):
        if not isinstance(value, six.string_types):
            raise ValidationError(_("Please specify a case property name."))

        value = value.strip()
        if not value:
            raise ValidationError(_("Please specify a case property name."))

        if value.startswith('/'):
            raise ValidationError(_("Case property names cannot start with a '/'"))

        return value

    def clean_conditions(self):
        result = []
        value = self.cleaned_data.get('conditions')
        try:
            value = json.loads(value)
        except:
            raise ValidationError(_("Invalid JSON"))

        valid_match_types = [choice[0] for choice in AutomaticUpdateRuleCriteria.MATCH_TYPE_CHOICES]

        for obj in value:
            property_name = self._clean_case_property_name(obj.get('property_name'))

            property_match_type = obj.get('property_match_type')
            if property_match_type not in valid_match_types:
                raise ValidationError(_("Invalid match type given"))

            property_value = None
            if property_match_type != AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE:
                property_value = obj.get('property_value')
                if not isinstance(property_value, six.string_types):
                    raise ValidationError(_("Please specify a property value."))

                property_value = property_value.strip()
                property_value = self.remove_quotes(property_value)
                if not property_value:
                    raise ValidationError(_("Please specify a property value."))

                if property_match_type in (
                    AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
                    AutomaticUpdateRuleCriteria.MATCH_DAYS_BEFORE,
                ):
                    try:
                        property_value = int(property_value)
                    except:
                        raise ValidationError(_("Please enter a number of days that is a number."))

            result.append(dict(
                property_name=property_name,
                property_match_type=property_match_type,
                property_value=property_value,
            ))
        return result

    def _closes_case(self):
        return self.cleaned_data.get('action') in [
            self.ACTION_UPDATE_AND_CLOSE,
            self.ACTION_CLOSE,
        ]

    def _updates_case(self):
        return self.cleaned_data.get('action') in [
            self.ACTION_UPDATE_AND_CLOSE,
            self.ACTION_UPDATE,
        ]

    def clean_update_property_name(self):
        if self._updates_case():
            return self._clean_case_property_name(self.cleaned_data.get('update_property_name'))

        return None

    def clean_update_property_value(self):
        value = None
        if self._updates_case():
            value = self.cleaned_data.get('update_property_value')
            value = self.remove_quotes(value)
            if not value:
                raise ValidationError(_("This field is required"))
        return value

    def clean_filter_on_server_modified(self):
        if not self.enhancements_enabled:
            return True
        else:
            string_value = self.cleaned_data.get('filter_on_server_modified')
            return json.loads(string_value)

    def clean_property_value_type(self):
        if not self.enhancements_enabled:
            return AutomaticUpdateAction.EXACT
        else:
            return self.cleaned_data.get('property_value_type')


class CaseUpdateRuleForm(forms.Form):
    # Prefix to avoid name collisions; this means all input
    # names in the HTML are prefixed with "rule-"
    prefix = "rule"

    name = TrimmedCharField(
        label=ugettext_lazy("Name"),
        required=True,
    )

    def compute_initial(self, rule):
        return {
            'name': rule.name,
        }

    def __init__(self, domain, *args, **kwargs):
        if 'initial' in kwargs:
            raise ValueError("Initial values are set by the form")

        self.is_system_admin = kwargs.pop('is_system_admin', False)

        rule = kwargs.pop('rule', None)
        if rule:
            kwargs['initial'] = self.compute_initial(rule)

        super(CaseUpdateRuleForm, self).__init__(*args, **kwargs)

        self.domain = domain
        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
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
        label=ugettext_lazy("Case Type"),
        required=True,
    )

    filter_on_server_modified = forms.CharField(required=False, initial='false')
    server_modified_boundary = forms.CharField(required=False, initial='')
    custom_match_definitions = forms.CharField(required=False, initial='[]')
    property_match_definitions = forms.CharField(required=False, initial='[]')
    filter_on_closed_parent = forms.CharField(required=False, initial='false')

    @property
    def current_values(self):
        return {
            'filter_on_server_modified': self['filter_on_server_modified'].value(),
            'server_modified_boundary': self['server_modified_boundary'].value(),
            'custom_match_definitions': json.loads(self['custom_match_definitions'].value()),
            'property_match_definitions': json.loads(self['property_match_definitions'].value()),
            'filter_on_closed_parent': self['filter_on_closed_parent'].value(),
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
        }

    def compute_initial(self, rule):
        initial = {
            'case_type': rule.case_type,
            'filter_on_server_modified': 'true' if rule.filter_on_server_modified else 'false',
            'server_modified_boundary': rule.server_modified_boundary,
        }

        custom_match_definitions = []
        property_match_definitions = []

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

        initial['custom_match_definitions'] = json.dumps(custom_match_definitions)
        initial['property_match_definitions'] = json.dumps(property_match_definitions)
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

    def __init__(self, domain, *args, **kwargs):
        if 'initial' in kwargs:
            raise ValueError("Initial values are set by the form")

        self.is_system_admin = kwargs.pop('is_system_admin', False)

        self.initial_rule = kwargs.pop('rule', None)
        if self.initial_rule:
            kwargs['initial'] = self.compute_initial(self.initial_rule)

        super(CaseRuleCriteriaForm, self).__init__(*args, **kwargs)

        self.domain = domain
        self.set_case_type_choices(self.initial.get('case_type'))

        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Fieldset(
                _("Case Filters") if self.show_fieldset_title else "",
                HTML(
                    '<p class="help-block"><i class="fa fa-info-circle"></i> %s</p>' % self.fieldset_help_text
                ),
                hidden_bound_field('filter_on_server_modified'),
                hidden_bound_field('server_modified_boundary'),
                hidden_bound_field('custom_match_definitions'),
                hidden_bound_field('property_match_definitions'),
                hidden_bound_field('filter_on_closed_parent'),
                Div(data_bind="template: {name: 'case-filters'}"),
                css_id="rule-criteria",
            ),
        )

        self.case_type_helper = FormHelper()
        self.case_type_helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.case_type_helper.field_class = 'col-xs-2'
        self.case_type_helper.form_tag = False
        self.case_type_helper.layout = Layout(Field('case_type'))

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
        raise ValueError("Invalid JSON object given")

    def set_case_type_choices(self, initial):
        case_types = [''] + list(get_case_types_for_domain_es(self.domain))
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
            if not name or name not in settings.AVAILABLE_CUSTOM_RULE_CRITERIA:
                raise ValidationError(_("Invalid custom filter id reference"))

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
                'property_name' not in obj or
                'property_value' not in obj or
                'match_type' not in obj
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

        return result

    def clean_filter_on_closed_parent(self):
        return true_or_false(self.cleaned_data.get('filter_on_closed_parent'))

    def save_criteria(self, rule):
        with transaction.atomic():
            rule.case_type = self.cleaned_data['case_type']
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

            if self.cleaned_data['filter_on_closed_parent']:
                definition = ClosedParentDefinition.objects.create()

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

    def compute_initial(self, rule):
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
            raise ValueError("Initial values are set by the form")

        self.is_system_admin = kwargs.pop('is_system_admin', False)

        rule = kwargs.pop('rule', None)
        if rule:
            kwargs['initial'] = self.compute_initial(rule)

        super(CaseRuleActionsForm, self).__init__(*args, **kwargs)

        self.domain = domain

        self.helper = FormHelper()
        self.helper.label_class = 'col-xs-2 col-xs-offset-1'
        self.helper.field_class = 'col-xs-2'
        self.helper.form_tag = False
        self.helper.form_show_errors = False
        self.helper.layout = Layout(
            Fieldset(
                _("Actions"),
                hidden_bound_field('close_case'),
                hidden_bound_field('properties_to_update'),
                hidden_bound_field('custom_action_definitions'),
                Div(data_bind="template: {name: 'case-actions'}"),
                css_id="rule-actions",
            ),
        )

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
                'name' not in obj or
                'value_type' not in obj or
                'value' not in obj
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
            if not name or name not in settings.AVAILABLE_CUSTOM_RULE_ACTIONS:
                raise ValidationError(_("Invalid custom action id reference"))

            result.append({
                'name': name
            })

        return result

    def clean(self):
        cleaned_data = super(CaseRuleActionsForm, self).clean()
        if (
            'close_case' in cleaned_data and
            'properties_to_update' in cleaned_data and
            'custom_action_definitions' in cleaned_data
        ):
            # All fields passed individual validation
            if (
                not cleaned_data['close_case'] and
                not cleaned_data['properties_to_update'] and
                not cleaned_data['custom_action_definitions']
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
