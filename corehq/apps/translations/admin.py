from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from corehq.apps.domain.dbaccessors import domain_exists
from corehq.apps.translations.models import AITranslationConfig


class AITranslationConfigForm(forms.ModelForm):
    class Meta:
        model = AITranslationConfig
        fields = '__all__'

    def clean_domain(self):
        domain = self.cleaned_data['domain']
        if not domain_exists(domain):
            raise ValidationError(f'Domain "{domain}" does not exist.')
        return domain

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('provider') and not cleaned.get('model'):
            # a provider-only row is ignored by get_model_config()
            self.add_error('model', 'model is required when provider is set.')
        return cleaned


@admin.register(AITranslationConfig)
class AITranslationConfigAdmin(admin.ModelAdmin):
    form = AITranslationConfigForm
    list_display = ('domain', 'lang', 'provider', 'model', 'monthly_word_limit')
    search_fields = ('domain',)
    readonly_fields = ('last_modified',)
