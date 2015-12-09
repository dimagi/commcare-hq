import json
from corehq.apps.data_interfaces.models import AutomaticUpdateRuleCriteria
from couchdbkit import ResourceNotFound
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
                mark_safe('<i class="icon-plus"></i> %s' % _("Create Group")),
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
                'case_identifier',
                css_class='input-xlarge'
            ),
            StrictButton(
                mark_safe('<i class="icon-plus"></i> %s' % _("Add Case")),
                css_class='btn-success',
                type="submit"
            )
        )


class AddAutomaticCaseUpdateRuleForm(forms.Form):
    ACTION_CLOSE = 'CLOSE'
    ACTION_UPDATE_AND_CLOSE = 'UPDATE_AND_CLOSE'

    name = TrimmedCharField(
        label=ugettext_lazy("Name"),
        required=True,
    )
    case_type = TrimmedCharField(
        label=ugettext_lazy("Case Type"),
        required=True,
    )
    server_modified_boundary = forms.IntegerField(
        required=True,
    )
    conditions = forms.CharField(
        required=True,
    )
    action = forms.ChoiceField(
        label=ugettext_lazy("When all conditions match"),
        choices=(
            (ACTION_CLOSE,
                ugettext_lazy("close the case")),
            (ACTION_UPDATE_AND_CLOSE,
                ugettext_lazy("set a case property and then close the case")),
        ),
    )
    update_property_name = TrimmedCharField(
        label=ugettext_lazy("Property"),
        required=False,
    )
    update_property_value = TrimmedCharField(
        label=ugettext_lazy("Value"),
        required=False,
    )

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

    def __init__(self, *args, **kwargs):
        super(AddAutomaticCaseUpdateRuleForm, self).__init__(*args, **kwargs)
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
            ),
            Fieldset(
                _("Conditions"),
                Field(
                    'conditions',
                    type='hidden',
                    ng_value='conditions',
                ),
                Div(ng_include='', src="'conditions.tpl'"),
            ),
            Fieldset(
                _("Action"),
                Field(
                    'action',
                    ng_model='action',
                ),
                Div(
                    Field(
                        'update_property_name',
                        ng_model='update_property_name',
                    ),
                    Field(
                        'update_property_value',
                        ng_model='update_property_value',
                    ),
                    ng_show='showUpdateProperty()',
                ),
            ),
            FormActions(
                StrictButton(
                    _("Save"),
                    type='submit',
                    css_class='btn btn-primary col-sm-offset-1'
                ),
            ),
        )

    def clean_server_modified_boundary(self):
        value = self.cleaned_data.get('server_modified_boundary')
        if not isinstance(value, int) or value < 30:
            raise ValidationError(_("Please enter a whole number greater than 30"))
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

            property_value = obj.get('property_value')
            if not isinstance(property_value, basestring):
                raise ValidationError(_("Please specify a property value."))

            property_value = property_value.strip()
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

    def _updates_case(self):
        return self.cleaned_data.get('action') == self.ACTION_UPDATE_AND_CLOSE

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
            if not value:
                raise ValidationError(_("This field is required"))
        return value
