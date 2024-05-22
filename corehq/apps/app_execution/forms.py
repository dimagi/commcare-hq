from couchdbkit import NoResultFound, ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField
from django import forms

from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username


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
        username = self.cleaned_data.get("username")
        if username and "@" not in username:
            try:
                username = normalize_username(self.cleaned_data.get("username"), domain)
            except ValueError:
                self.add_error("username", "Invalid username")
        try:
            self.commcare_user = CommCareUser.get_by_username(username)
        except ResourceNotFound:
            self.add_error("username", "User not found")

        if not self.commcare_user or self.commcare_user.domain != domain:
            self.add_error("username", f"User not found: {domain}")

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
