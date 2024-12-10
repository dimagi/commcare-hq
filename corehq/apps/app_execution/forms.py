from couchdbkit import NoResultFound, ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField
from django import forms
from django.utils.translation import gettext as _

from corehq.apps.app_execution.exceptions import AppExecutionError
from corehq.apps.app_execution.models import AppWorkflowConfig
from corehq.apps.app_execution.workflow_dsl import dsl_to_workflow, workflow_to_dsl
from corehq.apps.app_manager.dbaccessors import get_brief_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import generate_mobile_username


class AppWorkflowConfigForm(forms.ModelForm):
    run_every = forms.IntegerField(min_value=1, required=False, label=_("Run Every (minutes)"))
    username = forms.CharField(max_length=255, label=_("Username"),
                               help_text=_("Username of the user to run the workflow"))
    har_file = forms.FileField(label=_("HAR File"), required=False)
    workflow_dsl = forms.CharField(
        label="Workflow",
        required=False,
        widget=forms.Textarea(attrs={"rows": 20, "class": "textarea form-control"})
    )

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
        self.is_raw_mode = request.GET.get("mode", "dsl") == "raw"
        if self.is_raw_mode:
            del self.fields["workflow_dsl"]
        else:
            del self.fields["workflow"]
            workflow = self.instance.workflow
            if not workflow:
                workflow = self.initial.get("workflow")
            self.fields["workflow_dsl"].initial = workflow_to_dsl(workflow)

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

        har_help = _("HAR file recording should start with the selection of the app (navigate_menu_start).")
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Div(
                    *fields,
                    css_class="col",
                ),
                crispy.Div(
                    crispy.HTML(f"<p>{har_help}</p>"),
                    "har_file",
                    twbscrispy.StrictButton(
                        _("Populate workflow from HAR file"),
                        type='submit', css_class='btn-secondary', name="import_har", value="1",
                        formnovalidate=True,
                    ),
                    crispy.HTML("<p>&nbsp;</p>"),
                    crispy.HTML(f"<p>{_('Workflow:')}</p>"),
                    InlineField("workflow") if self.is_raw_mode else InlineField("workflow_dsl"),
                    css_class="col"
                ),
                css_class="row mb-3"
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(_("Save"), type='submit', css_class='btn-primary')
            ),
        )

    def clean_workflow_dsl(self):
        if "workflow_dsl" in self.cleaned_data:
            dsl = self.cleaned_data["workflow_dsl"]
            try:
                dsl_to_workflow(dsl)
            except AppExecutionError as e:
                raise forms.ValidationError(str(e))
            return dsl

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
            raise forms.ValidationError(_("App not found in domain: {domain}:{app_id}").format(
                domain=domain, app_id=app_id
            ))

        return app_id

    def clean(self):
        if "workflow_dsl" in self.cleaned_data:
            workflow = dsl_to_workflow(self.cleaned_data["workflow_dsl"])
            self.cleaned_data["workflow"] = workflow
        return self.cleaned_data

    def save(self, commit=True):
        self.instance.domain = self.request.domain
        self.instance.django_user = self.commcare_user.get_django_user()
        return super().save(commit=commit)
