from __future__ import absolute_import
import copy
from corehq.apps.groups.fields import GroupField
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.performance_sms import parser
from corehq.apps.performance_sms.exceptions import InvalidParameterException
from corehq.apps.performance_sms.models import TemplateVariable, ScheduleConfiguration, SCHEDULE_CHOICES, \
    PerformanceConfiguration
from corehq.apps.reports.daterange import get_simple_dateranges
from corehq.apps.userreports.ui.fields import JsonField
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
import corehq.apps.hqwebapp.crispy as hqcrispy
import six


class PerformanceFormMixin(object):

    def clean_template(self):
        return _clean_template(self.cleaned_data['template'])

    def clean(self):
        cleaned_data = super(PerformanceFormMixin, self).clean()
        if self.errors:
            # don't bother processing if there are already errors
            return cleaned_data
        config = PerformanceConfiguration.wrap(self.config.to_json())
        self._apply_updates_to_config(config, cleaned_data)
        try:
            config.validate()
        except InvalidParameterException as e:
            raise forms.ValidationError(six.text_type(e))

        return cleaned_data

    def save(self, commit=True):
        self._apply_updates_to_config(self.config, self.cleaned_data)
        if commit:
            self.config.save()
        return self.config

    def _apply_updates_to_config(self, config, cleaned_data):
        # overridden by subclasses
        raise NotImplementedError()


class PerformanceMessageEditForm(PerformanceFormMixin, forms.Form):
    recipient_id = forms.CharField()
    schedule_interval = forms.ChoiceField(
        choices=[(choice, ugettext_lazy(choice)) for choice in SCHEDULE_CHOICES]
    )
    template = forms.CharField(widget=forms.Textarea)
    time_range = forms.ChoiceField(
        choices=[(choice.slug, choice.description) for choice in get_simple_dateranges()]
    )

    def __init__(self, domain, config, *args, **kwargs):
        self.domain = domain
        self.config = config

        def _to_initial(config):
            initial = copy.copy(config._doc)
            initial['schedule_interval'] = config.schedule.interval
            if config.template_variables:
                initial['application'] = config.template_variables[0].app_id
                initial['source'] = config.template_variables[0].source_id
                initial['time_range'] = config.template_variables[0].time_range
            return initial

        super(PerformanceMessageEditForm, self).__init__(initial=_to_initial(config), *args, **kwargs)

        self.fields['recipient_id'] = GroupField(domain=domain, label=_('Recipient Group'))

        self.app_source_helper = ApplicationDataSourceUIHelper(enable_cases=False)
        self.app_source_helper.bootstrap(self.domain)
        data_source_fields = self.app_source_helper.get_fields()
        self.fields.update(data_source_fields)

        self.helper = _get_default_form_helper()
        form_layout = list(self.fields)
        form_layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Save Changes"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
            )
        )
        self.helper.layout = Layout(
            *form_layout
        )

    def _apply_updates_to_config(self, config, cleaned_data):
        config.recipient_id = cleaned_data['recipient_id']
        config.schedule = ScheduleConfiguration(interval=cleaned_data['schedule_interval'])
        config.template = cleaned_data['template']
        template_variable = TemplateVariable(
            type=cleaned_data['source_type'],
            time_range=cleaned_data['time_range'],
            source_id=cleaned_data['source'],
            app_id=cleaned_data['application'],
        )
        config.template_variables = [template_variable]
        return config

    @property
    def app_id(self):
        if self.config.template_variables:
            return self.config.template_variables[0].app_id
        return ''

    @property
    def source_id(self):
        if self.config.template_variables:
            return self.config.template_variables[0].source_id
        return ''


def _get_default_form_helper():
    helper = FormHelper()
    helper.label_class = 'col-sm-3 col-md-2'
    helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
    helper.form_class = "form-horizontal"
    helper.form_id = "performance-form"
    helper.form_method = 'post'
    return helper


def _clean_template(template):
    try:
        parser.validate(template)
    except InvalidParameterException as e:
        raise forms.ValidationError(six.text_type(e))
    return template


class AdvancedPerformanceMessageEditForm(PerformanceFormMixin, forms.Form):
    recipient_id = forms.CharField()
    schedule = JsonField()
    template = forms.CharField(widget=forms.Textarea)
    template_variables = JsonField(expected_type=list)

    def __init__(self, domain, config, *args, **kwargs):
        self.domain = domain
        self.config = config
        super(AdvancedPerformanceMessageEditForm, self).__init__(initial=config.to_json(), *args, **kwargs)

        self.fields['recipient_id'] = GroupField(domain=domain, label=_('Recipient Group'))

        self.helper = _get_default_form_helper()
        form_layout = list(self.fields)
        form_layout.append(
            hqcrispy.FormActions(
                StrictButton(
                    _("Save Changes"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
            )
        )
        self.helper.layout = Layout(
            *form_layout
        )

    def clean_schedule(self):
        return ScheduleConfiguration.wrap(self.cleaned_data['schedule'])

    def _apply_updates_to_config(self, config, cleaned_data):
        config.recipient_id = cleaned_data['recipient_id']
        config.schedule = cleaned_data['schedule']
        config.template = cleaned_data['template']
        config.template_variables = cleaned_data['template_variables']
        return config

    def clean_template_variables(self):
        template_vars = self.cleaned_data['template_variables']
        if not isinstance(template_vars, list):
            raise forms.ValidationError(_('Template variables must be a list!'))
        wrapped_vars = []
        for var in template_vars:
            try:
                wrapped = TemplateVariable.wrap(var)
                wrapped.validate()
                wrapped_vars.append(wrapped)
            except Exception as e:
                raise forms.ValidationError(_(u'Problem wrapping template variable! {}').format(e))
        return wrapped_vars
