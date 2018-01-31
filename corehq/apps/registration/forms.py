from __future__ import absolute_import
from captcha.fields import CaptchaField
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ugettext

from corehq.apps.programs.models import Program
from corehq.apps.users.models import CouchUser
from corehq.apps.users.forms import RoleForm, SupplyPointSelectWidget
from corehq.apps.domain.forms import clean_password, NoAutocompleteMixin
from corehq.apps.domain.models import Domain
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.hqwebapp.utils import decode_password

# https://docs.djangoproject.com/en/dev/topics/i18n/translation/#other-uses-of-lazy-in-delayed-translations
from django.utils.functional import lazy
import six
import re

from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy

mark_safe_lazy = lazy(mark_safe, six.text_type)


class RegisterWebUserForm(forms.Form):
    # Use: NewUserRegistrationView
    # Not inheriting from other forms to de-obfuscate the role of this form.

    full_name = forms.CharField(label=_("Full Name"))
    email = forms.CharField(label=_("Email"))
    password = forms.CharField(
        label=_("Create Password"),
        widget=forms.PasswordInput(),
    )
    phone_number = forms.CharField(
        label=_("Include area code or any other prefix"),
        required=False,
    )
    persona = forms.ChoiceField(
        label=_("I will primarily be using CommCare to..."),
        required=False,
        widget=forms.RadioSelect,
        choices=(
            (u"M&E", _("Monitor and evaluate a program")),
            (u"Improve Delivery", _("Improve delivery of services")),
            (u"Research", _("Collect data for a research project")),
            (u"IT", _("Build a technology solution for my team/clients")),
            (u"Other", _("Other")),
        )
    )
    persona_other = forms.CharField(
        required=False,
        label=_("Please Specify"),
    )
    project_name = forms.CharField(label=_("Project Name"))
    eula_confirmed = forms.BooleanField(
        required=False,
        label=mark_safe_lazy(_(
            """I have read and agree to the
            <a data-toggle='modal'
               data-target='#eulaModal'
               href='#eulaModal'>
               CommCare HQ End User License Agreement</a>.""")))
    atypical_user = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.show_phone_number = kwargs.pop('show_number', False)
        super(RegisterWebUserForm, self).__init__(*args, **kwargs)

        if not self.show_phone_number:
            del self.fields['phone_number']
            phone_number_fields = []
        else:
            phone_number_fields = [
                hqcrispy.InlineField(
                    'phone_number',
                    css_class="input-lg",
                    data_bind="value: phoneNumber, "
                              "valueUpdate: 'keyup'"
                ),
            ]

        persona_fields = [
            crispy.Div(
                hqcrispy.RadioSelect(
                    'persona',
                    css_class="input-lg",
                    data_bind="checked: personaChoice, "
                ),
                data_bind="css: {"
                          " 'has-success': isPersonaChoiceChosen, "
                          " 'has-error': isPersonaChoiceNeeded"
                          "}",
            ),
            hqcrispy.InlineField(
                'persona_other',
                css_class="input-lg",
                data_bind="value: personaOther, "
                          "visible: isPersonaChoiceOther",
            ),
        ]

        self.helper = FormHelper()
        self.helper.form_tag = False

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Fieldset(
                    _('Create Your Account'),
                    hqcrispy.FormStepNumber(1, 2),
                    hqcrispy.InlineField(
                        'full_name',
                        css_class="input-lg",
                        data_bind="value: fullName, "
                                  "valueUpdate: 'keyup', "
                                  "koValidationStateFeedback: { "
                                  "   validator: fullName "
                                  "}"
                    ),
                    hqcrispy.InlineField(
                        'email',
                        css_class="input-lg",
                        data_bind="value: email, "
                                  "valueUpdate: 'keyup', "
                                  "koValidationStateFeedback: { "
                                  "  validator: email, "
                                  "  delayedValidator: emailDelayed "
                                  "}",
                    ),
                    crispy.HTML('<p class="validation-message-block" '
                                'data-bind="visible: isEmailValidating, '
                                'text: validatingEmailMsg">&nbsp;</p>'),
                    hqcrispy.ValidationMessage('emailDelayed'),
                    hqcrispy.InlineField(
                        'password',
                        css_class="input-lg",
                        autocomplete="new-password",
                        data_bind="value: password, "
                                  "valueUpdate: 'keyup', "
                                  "koValidationStateFeedback: { "
                                  "   validator: password, "
                                  "   delayedValidator: passwordDelayed "
                                  "}",
                    ),
                    hqcrispy.ValidationMessage('passwordDelayed'),
                    crispy.Div(*phone_number_fields),
                    hqcrispy.InlineField('atypical_user'),
                    twbscrispy.StrictButton(
                        ugettext("Next"),
                        css_class="btn btn-success btn-lg",
                        data_bind="click: nextStep, disable: disableNextStepOne"
                    ),
                    css_class="check-password",
                ),
                css_class="form-step step-1",
                style="display: none;"
            ),
            crispy.Div(
                crispy.Fieldset(
                    _('Name Your First Project'),
                    hqcrispy.FormStepNumber(2, 2),
                    hqcrispy.InlineField(
                        'project_name',
                        css_class="input-lg",
                        data_bind="value: projectName, "
                                  "valueUpdate: 'keyup', "
                                  "koValidationStateFeedback: { "
                                  "   validator: projectName "
                                  "}",
                    ),
                    crispy.Div(*persona_fields),
                    hqcrispy.InlineField(
                        'eula_confirmed',
                        css_class="input-lg",
                        data_bind="checked: eulaConfirmed"
                    ),
                    twbscrispy.StrictButton(
                        ugettext("Previous"),
                        css_class="btn btn-primary-dark btn-lg",
                        data_bind="click: previousStep"
                    ),
                    twbscrispy.StrictButton(
                        ugettext("Finish"),
                        css_class="btn btn-success btn-lg",
                        data_bind="click: submitForm, "
                                  "disable: disableNextStepTwo"
                    )
                ),
                css_class="form-step step-2",
                style="display: none;"
            ),
        )

    def clean_full_name(self):
        data = self.cleaned_data['full_name'].split()
        return [data.pop(0)] + [' '.join(data)]

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        phone_number = re.sub('\s|\+|\-', '', phone_number)
        if phone_number == '':
            return None
        elif not re.match(r'\d+$', phone_number):
            raise forms.ValidationError(ugettext(
                "%s is an invalid phone number." % phone_number
            ))
        return phone_number

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)
        duplicate = CouchUser.get_by_username(data)
        if duplicate:
            # sync django user
            duplicate.save()
        if User.objects.filter(username__iexact=data).count() > 0 or duplicate:
            raise forms.ValidationError('Username already taken; please try another')
        return data

    def clean_password(self):
        return clean_password(decode_password(self.cleaned_data.get('password')))

    def clean_eula_confirmed(self):
        data = self.cleaned_data['eula_confirmed']
        if data is not True:
            raise forms.ValidationError(
                "You must agree to our End User License Agreement in order "
                "to register an account."
            )
        return data

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], six.string_types):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data


class DomainRegistrationForm(forms.Form):
    """
    Form for creating a domain for the first time
    """
    max_name_length = 25

    org = forms.CharField(widget=forms.HiddenInput(), required=False)
    hr_name = forms.CharField(label=_('Project Name'), max_length=max_name_length,
                                      widget=forms.TextInput(attrs={'class': 'form-control',
                                        'placeholder': _('My CommCare Project')}))

    def __init__(self, *args, **kwargs):
        super(DomainRegistrationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-6 col-md-5 col-lg-3'
        self.helper.layout = crispy.Layout(
            'hr_name',
            'org',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Create Project"),
                    type="submit",
                    css_class="btn btn-primary btn-lg disable-on-submit",
                )
            )
        )

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], six.string_types):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data


class WebUserInvitationForm(NoAutocompleteMixin, DomainRegistrationForm):
    """
    Form for a brand new user, before they've created a domain or done anything on CommCare HQ.
    """
    full_name = forms.CharField(label=_('Full Name'),
                                max_length=User._meta.get_field('first_name').max_length +
                                           User._meta.get_field('last_name').max_length + 1,
                                widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label=_('Email Address'),
                             max_length=User._meta.get_field('email').max_length,
                             help_text=_('You will use this email to log in.'),
                             widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label=_('Create Password'),
                               widget=forms.PasswordInput(render_value=False,
                                                          attrs={
                                                            'data-bind': "value: password, valueUpdate: 'input'",
                                                            'class': 'form-control',
                                                          }),
                               help_text=mark_safe("""
                               <span data-bind="text: passwordHelp, css: color">
                               """))
    if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
        captcha = CaptchaField(_("Type the letters in the box"))
    create_domain = forms.BooleanField(widget=forms.HiddenInput(), required=False, initial=False)
    # Must be set to False to have the clean_*() routine called
    eula_confirmed = forms.BooleanField(required=False,
                                        label="",
                                        help_text=mark_safe_lazy(_(
                                            """I have read and agree to the
                                               <a data-toggle='modal'
                                                  data-target='#eulaModal'
                                                  href='#eulaModal'>
                                                  CommCare HQ End User License Agreement
                                               </a>.""")))

    def __init__(self, *args, **kwargs):
        super(WebUserInvitationForm, self).__init__(*args, **kwargs)
        initial_create_domain = kwargs.get('initial', {}).get('create_domain', True)
        data_create_domain = self.data.get('create_domain', "True")
        if not initial_create_domain or data_create_domain == "False":
            self.fields['hr_name'].widget = forms.HiddenInput()

    def clean_full_name(self):
        data = self.cleaned_data['full_name'].split()
        return [data.pop(0)] + [' '.join(data)]

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)
        duplicate = CouchUser.get_by_username(data)
        if duplicate:
            # sync django user
            duplicate.save()
        if User.objects.filter(username__iexact=data).count() > 0 or duplicate:
            raise forms.ValidationError('Username already taken; please try another')
        return data

    def clean_password(self):
        try:
            return clean_password(self.cleaned_data.get('password'))
        except forms.ValidationError:
            track_workflow(self.cleaned_data.get('email'), 'Password Failure')
            raise

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], six.string_types):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

    def clean_eula_confirmed(self):
        data = self.cleaned_data['eula_confirmed']
        if data is not True:
            raise forms.ValidationError('You must agree to our End User License Agreement in order to register an account.')
        return data


# From http://www.peterbe.com/plog/automatically-strip-whitespace-in-django-app_manager
#
# I'll put this in each app, so they can be standalone, but it should really go in some centralized 
# part of the distro

class _BaseForm(object):

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], six.string_types):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data


class AdminInvitesUserForm(RoleForm, _BaseForm, forms.Form):
    # As above. Need email now; still don't need domain. Don't need TOS. Do need the is_active flag,
    # and do need to relabel some things.
    email       =  forms.EmailField(label="Email Address",
                                    max_length=User._meta.get_field('email').max_length)
#    is_domain_admin = forms.BooleanField(label='User is a domain administrator', initial=False, required=False)
    role = forms.ChoiceField(choices=(), label="Project Role")

    def __init__(self, data=None, excluded_emails=None, *args, **kwargs):
        domain = None
        location = None
        if 'domain' in kwargs:
            domain = Domain.get_by_name(kwargs['domain'])
            del kwargs['domain']
        if 'location' in kwargs:
            location = kwargs['location']
            del kwargs['location']
        super(AdminInvitesUserForm, self).__init__(data=data, *args, **kwargs)
        if domain and domain.commtrack_enabled:
            self.fields['supply_point'] = forms.CharField(label='Supply Point', required=False,
                                                          widget=SupplyPointSelectWidget(domain.name),
                                                          initial=location.location_id if location else '')
            self.fields['program'] = forms.ChoiceField(label="Program", choices=(), required=False)
            programs = Program.by_domain(domain.name, wrap=False)
            choices = list((prog['_id'], prog['name']) for prog in programs)
            choices.insert(0, ('', ''))
            self.fields['program'].choices = choices
        self.excluded_emails = excluded_emails or []

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email in self.excluded_emails:
            raise forms.ValidationError(_("A user with this email address is already in "
                                          "this project or has a pending invitation."))
        return email

