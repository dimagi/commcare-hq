from corehq.apps.receiverwrapper.models import FormRepeater, get_all_formats_in_repeater

from django import forms
from django.conf import settings
from dimagi.utils.modules import to_function


class GenericRepeaterForm(forms.Form):
    url = forms.URLField(
        required=True,
        label='URL to forward to',
        help_text='Please enter the full url, like http://www.example.com/forwarding/',
        widget=forms.TextInput(attrs={"class": "url"})
    )


class FormRepeaterForm(GenericRepeaterForm):
    exclude_device_reports = forms.BooleanField(
        required=False,
        label='Exclude device reports',
        initial=True
    )

    def __init__(self, *args, **kwargs):
        self.domain = kwargs.pop('domain')
        super(FormRepeaterForm, self).__init__(*args, **kwargs)

        self.formats = get_repeater_formats(FormRepeater, self.domain)

        if self.formats and len(self.formats) > 1:
            self.fields['format'] = forms.ChoiceField(
                required=True,
                label='Payload Format',
                choices=self.formats,
            )

    def clean(self):
        cleaned_data = super(FormRepeaterForm, self).clean()
        if 'format' not in cleaned_data:
            cleaned_data['format'] = self.formats[0][0]

        return cleaned_data


def get_repeater_formats(repeater, domain):
    formats = []
    for format_name, details in get_all_formats_in_repeater(repeater).iteritems():
        generator_cls = details['generator_cls']
        if generator_cls().enabled_for_domain(domain):
            formats.append((format_name, format_name))
    return formats