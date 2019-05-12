from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from django.utils.translation import (
    ugettext_lazy,
    ugettext as _,
)
from django.forms.widgets import Select
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from crispy_forms import layout as crispy

from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_version_build_id,
)
from corehq.apps.app_manager.exceptions import BuildNotFoundException
from corehq.motech.utils import (
    b64_aes_decrypt,
    b64_aes_encrypt,
)
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.hqwebapp import crispy as hqcrispy
from custom.icds.models import (
    CCZHosting,
    CCZHostingLink,
)


class CCZHostingLinkForm(forms.ModelForm):
    class Meta:
        model = CCZHostingLink
        exclude = ('domain',)

    def __init__(self, domain, *args, **kwargs):
        super(CCZHostingLinkForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        save_button_text = _('Update') if self.instance.pk else _('Create')
        self.helper.layout.append(Submit('save', save_button_text))
        if self.instance.pk:
            self.helper.layout.append(Submit('delete', _('Delete')))
        self.helper.layout = crispy.Fieldset(_("CCZ Hosting Link"), self.helper.layout)
        self.fields['identifier'].widget.attrs.update({'class': 'text-lowercase'})
        self.initial['password'] = b64_aes_decrypt(self.instance.password)
        self.instance.domain = domain

    def clean_password(self):
        return b64_aes_encrypt(self.cleaned_data['password'])


class CCZHostingForm(forms.Form):
    link_id = forms.ChoiceField(label=ugettext_lazy("Link"), choices=(), required=False)
    app_id = forms.ChoiceField(label=ugettext_lazy("Application"), choices=(), required=False)
    version = forms.IntegerField(label=ugettext_lazy('Version'), required=False, widget=Select(choices=[]))
    profile_id = forms.CharField(label=ugettext_lazy('Application Profile'),
                                 required=False, widget=Select(choices=[]))
    file_name = forms.CharField(label=ugettext_lazy("CCZ File Name"), required=False)

    def __init__(self, request, domain, *args, **kwargs):
        self.domain = domain
        super(CCZHostingForm, self).__init__(*args, **kwargs)
        self.fields['link_id'].choices = self.link_choices()
        self.fields['app_id'].choices = self.app_id_choices()
        self.helper = HQFormHelper()
        if request.GET.get('app_id'):
            self.fields['app_id'].initial = request.GET.get('app_id')
        if request.GET.get('link_id'):
            self.fields['link_id'].initial = request.GET.get('link_id')
        self.helper.layout = crispy.Layout(
            crispy.Field('link_id', css_class="hqwebapp-select2", id="link-id-select"),
            crispy.Field('app_id', css_class="hqwebapp-select2", id='app-id-search-select'),
            crispy.Field('version', id='version-input'),
            crispy.Field('profile_id', id='app-profile-id-input'),
            crispy.Field('file_name'),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Button('search', ugettext_lazy("Search"), data_bind="click: search"),
                    crispy.Button('clear', ugettext_lazy("Clear"), data_bind="click: clear"),
                    Submit('submit', ugettext_lazy("Create"))
                )
            )
        )

    def app_id_choices(self):
        choices = [(None, _('Select Application'))]
        for app in get_brief_apps_in_domain(self.domain):
            choices.append((app.id, app.name))
        return choices

    def link_choices(self):
        choices = [(None, _('Select Link'))]
        for link in CCZHostingLink.objects.filter(domain=self.domain):
            choices.append((link.id, link))
        return choices

    def _version_exists(self):
        return bool(get_version_build_id(self.domain, self.cleaned_data['app_id'],
                                         self.cleaned_data['version']))

    def clean_link_id(self):
        link_id = self.cleaned_data.get('link_id')
        if not link_id:
            self.add_error('link_id', _("Please select link"))
        return link_id

    def clean_app_id(self):
        app_id = self.cleaned_data.get('app_id')
        if not app_id:
            self.add_error('app_id', _("Please select application"))
        return app_id

    def clean_version(self):
        version = self.cleaned_data.get('version')
        if not version:
            self.add_error('version', _("Please select version"))
        return version

    def clean(self):
        if self.cleaned_data.get('app_id') and self.cleaned_data.get('version'):
            try:
                self._version_exists()
            except BuildNotFoundException as e:
                self.add_error('version', e)

    def save(self):
        try:
            CCZHosting.objects.create(
                link_id=self.cleaned_data['link_id'], app_id=self.cleaned_data['app_id'],
                version=self.cleaned_data['version'], profile_id=self.cleaned_data['profile_id'],
                file_name=self.cleaned_data['file_name']
            )
        except ValidationError as e:
            return False, ','.join(e.messages)
        return True, None
