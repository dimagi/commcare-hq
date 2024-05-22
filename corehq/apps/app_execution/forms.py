from couchdbkit import NoResultFound, ResourceNotFound
from django import forms

from corehq.apps.app_execution.data_model import AppWorkflow
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username


class AppWorkflowConfigForm(forms.ModelForm):
    run_every = forms.IntegerField(min_value=1, required=False, label="Run Every (minutes)")
    username = forms.CharField(
        max_length=255, label="Username", help_text="Username of the user to run the workflow"
    )
    har_file = forms.FileField(label="HAR File", required=False)
    workflow_simple = forms.CharField(
        label="Workflow",
        required=False,
        widget=forms.Textarea(attrs={"rows": 20, "class": "textarea form-control"})
    )
    edit_mode = forms.CharField(widget=forms.HiddenInput(), initial="simple")

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
            "workflow": forms.Textarea(attrs={"rows": 20, "class": "textarea form-control"}),
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        if self.instance.id:
            self.fields["username"].initial = self.instance.django_user.username
            self.fields["workflow_simple"].initial = self.instance.workflow_dsl
        self.helper = hqcrispy.HQFormHelper()
        self.helper.form_class = "form-horizontal"

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

    def clean(self):
        if self.cleaned_data.get("edit_mode") == "simple":
            try:
                workflow = AppWorkflow.from_dsl(self.cleaned_data.get("workflow_simple"))
            except Exception as e:
                self.add_error("workflow_simple", str(e))
            else:
                self.cleaned_data["workflow"] = workflow.to_json()
        return self.cleaned_data

    def save(self, commit=True):
        self.instance.domain = self.request.domain
        self.instance.django_user = self.commcare_user.get_django_user()
        return super().save(commit=commit)
