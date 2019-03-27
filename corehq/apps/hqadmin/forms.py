from __future__ import absolute_import
from __future__ import unicode_literals
import re
from memoized import memoized
from corehq.apps.hqwebapp.crispy import FormActions, FieldWithHelpBubble
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.apps.users.models import CommCareUser
from corehq.apps.hqwebapp import crispy as hqcrispy


class EmailForm(forms.Form):
    email_subject = forms.CharField(max_length=100)
    email_body_html = forms.CharField()
    email_body_text = forms.CharField()
    real_email = forms.BooleanField(required=False)


class AuthenticateAsForm(forms.Form):
    username = forms.CharField(max_length=255)
    domain = forms.CharField(label="Domain", max_length=255, required=False)

    @property
    @memoized
    def full_username(self):
        domain = self.cleaned_data['domain']
        if domain:
            return "{}@{}.commcarehq.org".format(self.cleaned_data['username'], domain)
        else:
            return self.cleaned_data['username']

    def clean(self):
        user = CommCareUser.get_by_username(username=self.full_username)
        if user is None:
            raise forms.ValidationError("Cannot find user '{}'".format(self.full_username))
        # Allowed only login as mobile user
        # web user would need stronger checks
        # https://github.com/dimagi/commcare-hq/pull/6940#issuecomment-108765585
        if not user.is_commcare_user():
            raise forms.ValidationError("User '{}' is not a CommCareUser".format(self.full_username))
        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        super(AuthenticateAsForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = 'auth-as-form'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'username',
            'domain',
            FormActions(
                crispy.Submit(
                    'authenticate_as',
                    'Authenticate As'
                )
            )
        )


class ReprocessMessagingCaseUpdatesForm(forms.Form):
    case_ids = forms.CharField(widget=forms.Textarea)

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
        label="Comma seperated email addresses",
        widget=forms.Textarea()
    )
    privileges = forms.MultipleChoiceField(
        choices=[
            ('is_superuser', 'Mark as superuser'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
    )

    def clean(self):
        from email.utils import parseaddr
        from django.contrib.auth.models import User
        csv_email_list = self.cleaned_data.get('csv_email_list', '')
        csv_email_list = csv_email_list.split(',')
        csv_email_list = [parseaddr(em)[1] for em in csv_email_list]
        if len(csv_email_list) > 10:
            raise forms.ValidationError(
                "This command is intended to grant superuser access to few users at a time. "
                "If you trying to update permissions for large number of users consider doing it via Django Admin"
            )

        users = []
        for username in csv_email_list:
            if "@dimagi.com" not in username:
                raise forms.ValidationError("Email address '{}' is not a dimagi email address".format(username))
            try:
                users.append(User.objects.get(username=username))
            except User.DoesNotExist:
                raise forms.ValidationError(
                    "User with email address '{}' does not exist on "
                    "this site, please have the user registered first".format(username))

        self.cleaned_data['users'] = users
        return self.cleaned_data

    def __init__(self, can_toggle_is_staff, *args, **kwargs):
        super(SuperuserManagementForm, self).__init__(*args, **kwargs)

        if can_toggle_is_staff:
            self.fields['privileges'].choices.append(
                ('is_staff', 'Mark as developer')
            )

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            'csv_email_list',
            'privileges',
            FormActions(
                crispy.Submit(
                    'superuser_management',
                    'Update privileges'
                )
            )
        )


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
