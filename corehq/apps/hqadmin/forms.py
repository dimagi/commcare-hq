import re
from django import forms
from django.core.exceptions import ValidationError


class EmailForm(forms.Form):
    email_subject = forms.CharField(max_length=100)
    email_body = forms.CharField()
    real_email = forms.BooleanField(required=False)


class BrokenBuildsForm(forms.Form):
    builds = forms.CharField(
        widget=forms.Textarea(attrs={'rows': '30', 'cols': '50'})
    )

    def clean_builds(self):
        self.build_ids = re.findall(r'[\w-]+', self.cleaned_data['builds'])
        if not self.build_ids:
            raise ValidationError("You must provide a ")
        return self.cleaned_data['builds']
