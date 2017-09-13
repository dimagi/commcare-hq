import re
from corehq.apps.hqwebapp.crispy import FormActions, FieldWithHelpBubble
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.apps.users.models import CommCareUser


class BrokenBuildsForm(forms.Form):
    builds = forms.CharField(
        widget=forms.Textarea(attrs={'rows': '30', 'cols': '50'})
    )

    def clean_builds(self):
        self.build_ids = re.findall(r'[\w-]+', self.cleaned_data['builds'])
        if not self.build_ids:
            raise ValidationError("You must provide a ")
        return self.cleaned_data['builds']


class AuthenticateAsForm(forms.Form):
    username = forms.CharField(max_length=255)
    domain = forms.CharField(label=u"Domain (used for mobile workers)", max_length=255, required=False)

    def clean(self):
        username = self.cleaned_data['username']
        domain = self.cleaned_data['domain']

        # Ensure that the username exists either as the raw input or with fully qualified name
        if domain:
            extended_username = u"{}@{}.commcarehq.org".format(username, domain)
            user = CommCareUser.get_by_username(username=extended_username)
            self.cleaned_data['username'] = extended_username
            if user is None:
                raise forms.ValidationError(
                    u"Cannot find user '{}' for domain '{}'".format(username, domain)
                )
        else:
            user = CommCareUser.get_by_username(username=username)
            if user is None:
                raise forms.ValidationError(u"Cannot find user '{}'".format(username))

        if not user.is_commcare_user():
            raise forms.ValidationError(u"User '{}' is not a CommCareUser".format(username))

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
                raise forms.ValidationError(u"Email address '{}' is not a dimagi email address".format(username))
            try:
                users.append(User.objects.get(username=username))
            except User.DoesNotExist:
                raise forms.ValidationError(
                    u"User with email address '{}' does not exist on "
                    "this site, please have the user registered first".format(username))

        self.cleaned_data['users'] = users
        return self.cleaned_data

    def __init__(self, can_toggle_is_staff, *args, **kwargs):
        super(SuperuserManagementForm, self).__init__(*args, **kwargs)

        if can_toggle_is_staff:
            self.fields['privileges'].choices.append(
                ('is_staff', 'mark as developer')
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
