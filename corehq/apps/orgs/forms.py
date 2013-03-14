from django import forms
from django.core.validators import validate_email
from corehq.apps.domain.models import Domain
import re
from corehq.apps.domain.utils import new_domain_re, website_re
from corehq.apps.orgs.models import Organization, Team
from corehq.apps.registration.forms import OrganizationRegistrationForm
from corehq.apps.users.models import CouchUser

class AddProjectForm(forms.Form):
    domain_name = forms.CharField(label="Project Name", help_text="e.g. - public")
    domain_hrname = forms.CharField(label="Project Nickname", required=False, help_text="e.g. - Commcare HQ Demo Project")

    def __init__(self, org_name, *args, **kwargs):
        self.org_name = org_name
        super(AddProjectForm, self).__init__(*args, **kwargs)

    def clean_domain_hrname(self):
        data = self.cleaned_data['domain_hrname']
        if not data:
            data = self.cleaned_data['domain_name']

        conflict = Domain.get_by_organization_and_hrname(self.org_name, data) or Domain.get_by_organization_and_hrname(self.org_name, data.replace('-', '.'))
        if conflict:
            raise forms.ValidationError('A project with that display name already exists.')
        return data

    def clean_domain_name(self):
        data = self.cleaned_data['domain_name'].strip().lower()
        if not Domain.get_by_name(data):
            raise forms.ValidationError('This project does not exist.')
        return data

class InviteMemberForm(forms.Form):
    email = forms.CharField(label = "User Email")

    def __init__(self, org_name, *args, **kwargs):
        self.org_name = org_name
        super(InviteMemberForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        data = self.cleaned_data['email'].strip().lower()
        validate_email(data)

        existing_member = CouchUser.get_by_username(data)
        if existing_member:
            org = Organization.get_by_name(self.org_name)
            for member in org.get_members():
                if member.get_id == existing_member.get_id:
                    raise forms.ValidationError('User is already part of this organization!')

        return data

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

#class AddMemberToTeamForm(forms.Form):
#
#    def __init__(self, org_name, *args, **kwargs):
#        super(AddMemberToTeamForm, self).__init__(*args, **kwargs)
#        self.teams = Team.get_by_org(org_name)
#        self.team_names = [team.name for team in self.teams]
#        self.team = forms.ChoiceField(label="Team", choices=self.team_names)
#        self.fields['teams'] = self.team
#
#    @property
#    def organization(self):
#        return self.org_name
#


class AddTeamForm(forms.Form):

    team = forms.CharField(label="Team Name", max_length=20)

    def __init__(self, org_name, *args, **kwargs):
        self.org_name = org_name
        super(AddTeamForm, self).__init__(*args, **kwargs)

    def clean_team(self):
        data = self.cleaned_data['team'].strip()
        org_teams = Team.get_by_org(self.org_name)
        for t in org_teams:
            if t.name == data:
                raise forms.ValidationError('A team with that name already exists.')
        return data


class UpdateOrgInfo(OrganizationRegistrationForm):
    def __init__(self, *args, **kwargs):
        # Value of 'kind' is irrelevant in this context
        super(UpdateOrgInfo, self).__init__(*args, **kwargs)
        del self.fields['org_name']
