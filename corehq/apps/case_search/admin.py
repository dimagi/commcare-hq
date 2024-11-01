from django import forms
from django.conf import settings
from django.contrib import admin
from django.forms.fields import BooleanField

from .models import CaseSearchConfig


class CaseSearchConfigForm(forms.ModelForm):
    index_name = BooleanField(label="Use dedicated index")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _construct_index_name(self.fields['index_name'], self.instance.domain)

    def clean_index_name(self):
        selected = self.cleaned_data['index_name']
        valid_index_name = _get_valid_index_name(self.cleaned_data['domain'])
        if selected and valid_index_name:
            return valid_index_name
        return ''


def _construct_index_name(field, domain):
    valid_index_name = _get_valid_index_name(domain)
    if valid_index_name:
        field.help_text = valid_index_name
    else:
        field.disabled = True
        field.help_text = "Not applicable, will be cleared on save"


def _get_valid_index_name(domain):
    return settings.CASE_SEARCH_SUB_INDICES.get(domain, {}).get('index_cname')


@admin.register(CaseSearchConfig)
class CaseSearchConfigAdmin(admin.ModelAdmin):
    list_display = ['domain', 'enabled']
    list_filter = ['domain', 'enabled']
    search_fields = ['domain']
    exclude = ['fuzzy_properties', 'ignore_patterns']
    form = CaseSearchConfigForm
