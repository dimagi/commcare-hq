from couchdbkit import NoResultFound, ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField
from django import forms
from django.utils.translation import gettext as _

from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import generate_mobile_username


class AppWorkflowConfigForm(forms.ModelForm):
    run_every = forms.IntegerField(min_value=1, required=False, label="Run Every (minutes)")
    username = forms.CharField(max_length=255, label="Username",
                               help_text="Username of the user to run the workflow")
    har_file = forms.FileField(label="HAR File", required=False)

    class Meta:
        model = AppWorkflowConfig
        fields = (
            "name",
            "app_id",
            "workflow",
            "sync_before_run",
            "form_mode",
            "run_every",
            "notification_emails"
        )
        widgets = {
            "form_mode": forms.RadioSelect(),
            "workflow": forms.Textarea(attrs={"rows": 20}),
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        if self.instance.id:
            self.fields["username"].initial = self.instance.django_user.username
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_class = "form-horizontal"

        fields = [
            "name",
            "app_id",
            "username",
            "sync_before_run",
            "form_mode",
        ]
        if request.user.is_superuser:
            fields += ["run_every", "notification_emails"]

        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    crispy.HTML("<p>&nbsp;</p>"),
                    *fields,
                    css_class="col",
                ),
                crispy.Div(
                    crispy.HTML("<p>Workflow:</p>"),
                    InlineField("workflow"),
                    css_class="col"
                ),
                css_class="row mb-3"
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton("Save", type='submit', css_class='btn-primary')
            ),
            "har_file",
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    "Import HAR", type='submit', css_class='btn-secondary', name="import_har", value="1",
                    formnovalidate=True,
                )
            ),
        )

    def clean_username(self):
        domain = self.request.domain
        username = generate_mobile_username(self.cleaned_data.get("username"), domain, is_unique=False)
        try:
            self.commcare_user = CommCareUser.get_by_username(username)
        except ResourceNotFound:
            raise forms.ValidationError(_("User not found"))

        if not self.commcare_user or self.commcare_user.domain != domain:
            raise forms.ValidationError(_("User not found"))

        return username

    def clean_app_id(self):
        domain = self.request.domain
        app_id = self.cleaned_data.get("app_id")
        try:
            get_brief_app(domain, app_id)
        except NoResultFound:
            raise forms.ValidationError(f"App not found in domain: {domain}:{app_id}")

        return app_id

    def save(self, commit=True):
        self.instance.domain = self.request.domain
        self.instance.django_user = self.commcare_user.get_django_user()
        return super().save(commit=commit)
