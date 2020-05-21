from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from corehq.apps.hqwebapp.crispy import HQFormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy
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
