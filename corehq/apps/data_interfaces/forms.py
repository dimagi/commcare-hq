import json
from corehq.apps.data_interfaces.models import AutomaticUpdateRuleCriteria
from corehq.apps.style import crispy as hqcrispy
from couchdbkit import ResourceNotFound

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import AUTO_CASE_UPDATES
from crispy_forms.bootstrap import StrictButton, InlineField, FormActions, FieldWithButtons
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, HTML, Div, Fieldset
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.casegroups.models import CommCareCaseGroup
from dimagi.utils.django.fields import TrimmedCharField


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
    server_modified_boundary = forms.IntegerField(
        label=ugettext_lazy("enter number of days"),
        required=True,
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
    update_property_value = TrimmedCharField(
        required=False,
    )

    def remove_quotes(self, value):
        if isinstance(value, basestring) and len(value) >= 2:
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
        case_types = [''] + list(CaseAccessors(self.domain).get_case_types())
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
        If the AUTO_CASE_UPDATES toggle is enabled for the domain, then
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
        super(AddAutomaticCaseUpdateRuleForm, self).__init__(*args, **kwargs)

        # We can't set these fields to be required because they are displayed
        # conditionally and we'll confuse django validation if we make them
        # required. However, we should show the asterisk for consistency, since
        # when they are displayed they are required.
        self.fields['update_property_name'].label = _("Property") + '<span class="asteriskField">*</span>'
        self.fields['update_property_value'].label = _("Value") + '<span class="asteriskField">*</span>'

        if AUTO_CASE_UPDATES.enabled(self.domain):
            self.allow_updates_without_closing()

        self.set_case_type_choices(self.initial.get('case_type'))
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.form_method = 'POST'
        self.helper.form_action = '#'
        self.helper.layout = Layout(
            Fieldset(
                _("Basic Information"),
                Field(
                    'name',
                    ng_model='name',
                ),
                Field(
                    'case_type',
                    ng_model='case_type',
                ),
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
                ),
                Field(
                    'action',
                    ng_model='action',
                ),
                Div(
                    Field(
                        'update_property_name',
                        ng_model='update_property_name',
                        css_class='case-property-typeahead',
                    ),
                    Field(
                        'update_property_value',
                        ng_model='update_property_value',
                    ),
                    ng_show='showUpdateProperty()',
                ),
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
        if not isinstance(value, int) or value < 30:
            raise ValidationError(_("Please enter a whole number greater than "
                                    "or equal to 30."))
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
            property_name = obj.get('property_name')
            if not isinstance(property_name, basestring):
                raise ValidationError(_("Please specify a property name."))

            property_name = property_name.strip()
            if not property_name:
                raise ValidationError(_("Please specify a property name."))

            property_match_type = obj.get('property_match_type')
            if property_match_type not in valid_match_types:
                raise ValidationError(_("Invalid match type given"))

            property_value = None
            if property_match_type != AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE:
                property_value = obj.get('property_value')
                if not isinstance(property_value, basestring):
                    raise ValidationError(_("Please specify a property value."))

                property_value = property_value.strip()
                property_value = self.remove_quotes(property_value)
                if not property_value:
                    raise ValidationError(_("Please specify a property value."))

                if property_match_type == AutomaticUpdateRuleCriteria.MATCH_DAYS_SINCE:
                    try:
                        property_value = int(property_value)
                    except:
                        raise ValidationError(_("Please enter a number of days that is a number."))

                    if property_value <= 0:
                        raise ValidationError(_("Please enter a number of days that is positive."))

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
        value = None
        if self._updates_case():
            value = self.cleaned_data.get('update_property_name')
            if not value:
                raise ValidationError(_("This field is required"))
        return value

    def clean_update_property_value(self):
        value = None
        if self._updates_case():
            value = self.cleaned_data.get('update_property_value')
            value = self.remove_quotes(value)
            if not value:
                raise ValidationError(_("This field is required"))
        return value
