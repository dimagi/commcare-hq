from django import forms
from django.utils.translation import gettext_lazy as _

from corehq.apps.campaign.models import DashboardTab


class DashboardWidgetBaseForm(forms.ModelForm):

    class Meta:
        fields = [
            'title',
            'description',
            'dashboard_tab',
            'display_order',
        ]

    title = forms.CharField(
        label=_('Title'),
        required=True,
    )
    description = forms.CharField(
        label=_('Description'),
        required=False,
    )
    dashboard_tab = forms.ChoiceField(
        label=_('Dashboard Tab'),
        choices=DashboardTab.choices
    )
    display_order = forms.IntegerField(
        label=_('Display Order'),
    )
