from django import forms
from corehq.apps.domain.models import Domain
import re
from corehq.apps.domain.utils import new_domain_re

class AddProjectForm(forms.Form):
    domain_name = forms.CharField(label="Project name")
    domain_slug = forms.CharField(label="New project name", help_text="""
This project will be given a new name within this organization. You may leave it the same or choose a new name.
""")

    def __init__(self, org_name, *args, **kwargs):
        self.org_name = org_name
        super(AddProjectForm, self).__init__(*args, **kwargs)

    def clean_domain_slug(self):
        data = self.cleaned_data['domain_slug'].strip().lower()

        if not re.match("^%s$" % new_domain_re, data):
            raise forms.ValidationError('Only lowercase letters and numbers allowed. Single hyphens may be used to separate words.')

        conflict = Domain.get_by_organization_and_slug(self.org_name, data) or Domain.get_by_organization_and_slug(self.org_name, data.replace('-', '.'))
        if conflict:
            raise forms.ValidationError('A project with that name already exists.')
        return data

    def clean_domain_name(self):
        data = self.cleaned_data['domain_name'].strip().lower()
        if not Domain.get_by_name(data):
            raise forms.ValidationError('This project does not exist.')
        return data