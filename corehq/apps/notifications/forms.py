from django import forms
from django.contrib.postgres.forms import SimpleArrayField
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy

from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.widgets import BootstrapCheckboxInput

from .models import NOTIFICATION_TYPES, Notification


class NotificationCreationForm(forms.Form):
    content = forms.CharField(
        label=gettext_lazy('Content'),
        max_length=140,
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )
    url = forms.URLField(
        label=gettext_lazy('URL')
    )
    type = forms.ChoiceField(
        label=gettext_lazy("Type"),
        choices=NOTIFICATION_TYPES,
    )
    domain_specific = forms.BooleanField(
        label=gettext_lazy("Domain-specific"),
        required=False,
        widget=BootstrapCheckboxInput(
            inline_label=gettext_lazy("This notification is not for all domains"),
        ),
    )
    domains = SimpleArrayField(
        base_field=forms.CharField(),
        label=gettext_lazy("Domains"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        help_text=gettext_lazy("Enter a comma separated list of domains for this notification. "
                               "This is only required if you have checked the box above."),
        required=False
    )

    def __init__(self, *args, **kwargs):
        from corehq.apps.notifications.views import ManageNotificationView
        super(NotificationCreationForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.helper.form_method = 'POST'
        self.helper.form_action = '#'

        self.helper.layout = crispy.Layout(
            crispy.Field('content'),
            crispy.Field('url'),
            crispy.Field('type'),
            twbscrispy.PrependedText('domain_specific', ''),
            crispy.Field('domains'),
            twbscrispy.StrictButton(
                _("Submit Information"),
                type="submit",
                css_class="btn btn-primary",
                name="submit",
            ),
            hqcrispy.LinkButton(
                _("Cancel"),
                reverse(ManageNotificationView.urlname),
                css_class="btn btn-outline-primary",
                name="cancel",
            ),
        )

    def save(self):
        data = self.cleaned_data
        Notification(content=data.get('content'),
                     url=data.get('url'),
                     type=data.get('type'),
                     domain_specific=data.get('domain_specific'),
                     domains=data.get('domains')).save()
