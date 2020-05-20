from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from corehq.apps.hqwebapp.crispy import HQFormHelper

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.dbaccessors import (
    get_linked_domains,
)


class CopyReportForm(forms.Form):

    def __init__(self, from_domain, report_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_domain = from_domain

        choices = [('', ugettext_lazy("Select a project..."))]
        choices.extend((d.linked_domain, d.linked_domain) for d in get_linked_domains(self.from_domain))
        self.fields['domain'] = forms.CharField(
            label=ugettext_lazy("Copy this report to project"),
            widget=forms.Select(choices=choices),
        )

        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            'domain',
            crispy.Hidden("report_id", report_id),
            hqcrispy.FormActions(StrictButton(_("Copy"), type="submit", css_class="btn-primary")),
        )

    def clean_domain(self):
        domain = self.cleaned_data["domain"]
        domain_obj = Domain.get_by_name(domain)
        if domain_obj is None:
            raise forms.ValidationError("A valid project space is required.")
        if toggles.MULTI_MASTER_BYPASS_VERSION_CHECK.enabled(domain):
            raise forms.ValidationError(
                """
                Copying an app to a domain that uses multi-master linked apps and bypasses
                the minimum CommCare version check requires developer intervention.
            """
            )
        return domain

    def clean(self):
        domain = self.cleaned_data.get("domain")
        if self.cleaned_data.get("linked"):
            if not toggles.LINKED_DOMAINS.enabled(domain):
                raise forms.ValidationError(
                    "The target project space does not have linked apps enabled."
                )
            link = DomainLink.objects.filter(linked_domain=domain)
            if link and link[0].master_domain != self.from_domain:
                raise forms.ValidationError(
                    "The target project space is already linked to a different domain"
                )
        return self.cleaned_data
