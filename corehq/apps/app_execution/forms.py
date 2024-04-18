from couchdbkit import NoResultFound, ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from django import forms

from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser


class AppWorkflowConfigForm(forms.ModelForm):

    class Meta:
        model = AppWorkflowConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.layout = crispy.Layout(
            *self.fields.keys(),
            hqcrispy.FormActions(
                twbscrispy.StrictButton("Save",
                                        type='submit',
                                        css_class='btn-primary'),
            ),
        )

    def clean(self):
        self.final_clean_app_id()
        self.final_clean_user_id()
        print(self.cleaned_data)
        return self.cleaned_data

    def final_clean_user_id(self):
        domain = self.cleaned_data.get("domain")
        try:
            CommCareUser.get_by_user_id(domain, self.cleaned_data.get("user_id"))
        except ResourceNotFound:
            raise forms.ValidationError(f"User not found in domain: {domain}:{self.cleaned_data.get('user_id')}")

    def final_clean_app_id(self):
        domain = self.cleaned_data.get("domain")
        app_id = self.cleaned_data.get("app_id")
        try:
            get_brief_app(domain, app_id)
        except NoResultFound:
            raise forms.ValidationError(f"App not found in domain: {domain}:{app_id}")
