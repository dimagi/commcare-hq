from couchdbkit import NoResultFound, ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms

from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser


class AppWorkflowConfigForm(forms.ModelForm):
    run_every = forms.IntegerField(min_value=1)

    class Meta:
        model = AppWorkflowConfig
        fields = (
            "name",
            "domain",
            "app_id",
            "user_id",
            "workflow",
            "sync_before_run",
            "form_mode",
            "run_every",
            "notification_emails"
        )
        widgets = {
            "form_mode": forms.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.layout = crispy.Layout(
            *self.fields.keys(),
            hqcrispy.FormActions(
                twbscrispy.StrictButton("Save", type='submit', css_class='btn-primary')
            ),
        )

    def clean(self):
        self.final_clean_app_id()
        self.final_clean_user_id()
        return self.cleaned_data

    def final_clean_user_id(self):
        domain = self.cleaned_data.get("domain")
        try:
            self.commcare_user = CommCareUser.get_by_user_id(self.cleaned_data.get("user_id"), domain)
        except ResourceNotFound:
            raise forms.ValidationError(f"User not found in domain: {domain}:{self.cleaned_data.get('user_id')}")

    def final_clean_app_id(self):
        domain = self.cleaned_data.get("domain")
        app_id = self.cleaned_data.get("app_id")
        try:
            get_brief_app(domain, app_id)
        except NoResultFound:
            raise forms.ValidationError(f"App not found in domain: {domain}:{app_id}")

    def save(self, commit=True):
        self.instance.django_user = self.commcare_user.get_django_user()
        return super().save(commit=commit)
