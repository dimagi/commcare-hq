import re

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db.models import Q

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import FieldWithHelpBubble, FormActions
from corehq.apps.users.util import is_dimagi_email

from email.utils import parseaddr


class EmailForm(forms.Form):
    email_subject = forms.CharField(max_length=100)
    email_body_html = forms.CharField()
    email_body_text = forms.CharField()
    real_email = forms.BooleanField(required=False)


class ReprocessMessagingCaseUpdatesForm(forms.Form):
    case_ids = forms.CharField(widget=forms.Textarea(attrs={"class": "vertical-resize"}))

    def clean_case_ids(self):
        value = self.cleaned_data.get('case_ids', '')
        value = value.split()
        if not value:
            raise ValidationError(_("This field is required."))
        return set(value)

    def __init__(self, *args, **kwargs):
        super(ReprocessMessagingCaseUpdatesForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = 'reprocess-messaging-updates'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8'
        self.helper.layout = crispy.Layout(
            FieldWithHelpBubble(
                'case_ids',
                help_bubble_text=_("Enter a space-separated list of case ids to reprocess. "
                    "Reminder rules will be rerun for the case, and the case's phone "
                    "number entries will be synced."),
            ),
            FormActions(
                crispy.Submit(
                    'submit',
                    'Submit'
                )
            )
        )


class SuperuserManagementForm(forms.Form):
    csv_email_list = forms.CharField(
        label="Comma or new-line separated email addresses",
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=True
    )
    privileges = forms.MultipleChoiceField(
        choices=[
            ('is_staff', 'Mark as developer'),
            ('is_superuser', 'Mark as superuser')
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )
    can_assign_superuser = forms.MultipleChoiceField(
        choices=[
            ('can_assign_superuser', 'Grant permission to change superuser and staff status')
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    def clean(self):
        return clean_data(self.cleaned_data)

    def __init__(self, *args, **kwargs):
        super(SuperuserManagementForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'csv_email_list',
            'privileges',
            'can_assign_superuser',
            FormActions(
                crispy.Submit(
                    'superuser_management',
                    'Update privileges'
                )
            )
        )


class OffboardingUserListForm(forms.Form):
    csv_email_list = forms.CharField(
        label="Comma/new-line seperated email addresses",
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False
    )

    def clean(self):
        return clean_data(self.cleaned_data, offboarding_list=True)

    def __init__(self, *args, **kwargs):
        super(OffboardingUserListForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'csv_email_list',
            FormActions(
                crispy.Submit(
                    'get_offboarding_list',
                    'Get Users Not in List'
                )
            )
        )


def clean_data(cleaned_data, offboarding_list=False):
    EMAIL_INDEX = 1
    csv_email_list = cleaned_data.get('csv_email_list', '')
    all_users = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True)
                                    | (Q(is_active=True) & Q(username__endswith='@dimagi.com')))
    if offboarding_list and not csv_email_list:
        cleaned_data['csv_email_list'] = all_users
        return cleaned_data

    csv_email_list = re.split(',|\n', csv_email_list)
    csv_email_list = [parseaddr(email)[EMAIL_INDEX] for email in csv_email_list]

    MAX_ALLOWED_EMAIL_USERS = 10
    users = []
    validation_errors = []

    # Superuser management
    non_dimagi_email = []
    if not offboarding_list:
        if len(csv_email_list) > MAX_ALLOWED_EMAIL_USERS:
            raise forms.ValidationError(
                f"This command allows superusers to modify up to {MAX_ALLOWED_EMAIL_USERS} users at a time. "
            )
        for username in csv_email_list:
            if settings.IS_DIMAGI_ENVIRONMENT and not is_dimagi_email(username):
                non_dimagi_email.append(ValidationError(username))
                continue
            try:
                users.append(User.objects.get(username=username))
            except User.DoesNotExist:
                validation_errors.append(ValidationError(username))
        if validation_errors or non_dimagi_email:
            if non_dimagi_email:
                non_dimagi_email.insert(0, ValidationError(
                    _("The following email addresses are not dimagi email addresses:")))
            if validation_errors:
                validation_errors.insert(0, ValidationError(
                    _("The following users do not exist on this site, please have the user registered first:")))
                if non_dimagi_email:
                    validation_errors.append('+')
            raise ValidationError(validation_errors + non_dimagi_email)

    # Offboarding list
    if offboarding_list:
        for username in csv_email_list:
            try:
                users.append(User.objects.get(username=username))
            except User.DoesNotExist:
                validation_errors.append(username)
        if validation_errors:
            cleaned_data['validation_errors'] = validation_errors

        # inverts the given list by default
        email_names = [username.split("@")[0] + "+" for username in csv_email_list]
        users = [user for user in all_users if user not in users
                 and not list(filter(user.username.startswith, email_names))]

    cleaned_data['csv_email_list'] = users
    return cleaned_data


class DisableTwoFactorForm(forms.Form):
    VERIFICATION = (
        ('in_person', 'In Person'),
        ('voice', 'By Voice'),
        ('video', 'By Video'),
        ('via_someone_else', 'Via another Dimagi Employee'),
    )
    username = forms.EmailField(label=_("Confirm the username"))
    verification_mode = forms.ChoiceField(
        choices=VERIFICATION, required=True, label="How was the request verified?"
    )
    via_who = forms.EmailField(
        label=_("Verified by"),
        required=False,
        help_text="If you verified the request via someone else please enter their email address."
    )
    disable_for_days = forms.IntegerField(
        label=_("Days to allow access"),
        min_value=0,
        max_value=30,
        help_text=_(
            "Number of days the user can access CommCare HQ before needing to re-enable two-factor auth."
            "This is useful if someone has lost their phone and can't immediately re-setup two-factor auth.")
    )

    def __init__(self, initial, **kwargs):
        self.username = initial.pop('username')
        super(DisableTwoFactorForm, self).__init__(initial=initial, **kwargs)
        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Basic Information"),
                crispy.Field('username'),
                crispy.Field('verification_mode'),
                crispy.Field('via_who'),
                crispy.Field('disable_for_days'),
            ),
            hqcrispy.FormActions(
                crispy.Submit(
                    "disable",
                    _("Disable"),
                    css_class="btn btn-danger",
                ),
                css_class='modal-footer',
            ),
        )

    def clean_username(self):
        username = self.cleaned_data['username']
        username = username.lower()
        if username != self.username:
            raise forms.ValidationError("Username doesn't match expected.")

        return username

    def clean(self):
        verification_mode = self.cleaned_data['verification_mode']
        if verification_mode == 'via_someone_else' and not self.cleaned_data['via_who']:
            raise forms.ValidationError({
                "via_who": "Please enter the email address of the person who verified the request."
            })

        return self.cleaned_data


class DisableUserForm(forms.Form):
    reason = forms.CharField(
        label=_("Reason"),
        help_text=_("Please give a reason for this action.")
    )
    reset_password = forms.BooleanField(
        label=_("Reset account password"),
        required=False,
        help_text=_("Resetting the user's password will force them to follow the 'Forgot Password' workflow."
                    " Use this if it is suspected that the password has been compromised.")
    )

    def __init__(self, initial, **kwargs):
        self.user = initial.pop('user')
        super(DisableUserForm, self).__init__(initial=initial, **kwargs)
        self.helper = FormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_action = '#'

        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        action = _("Disable") if self.user.is_active else _("Enable")
        css_class = 'btn-danger' if self.user.is_active else 'btn-primary'
        self.helper.layout = crispy.Layout(
            crispy.Field('reason'),
            crispy.Field('reset_password'),
            hqcrispy.FormActions(
                crispy.Submit(
                    "submit",
                    action,
                    css_class="btn %s" % css_class,
                ),
                css_class='modal-footer',
            ),
        )
