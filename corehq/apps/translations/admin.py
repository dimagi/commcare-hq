from django.contrib import admin

from corehq.apps.translations.models import AITranslationConfig


@admin.register(AITranslationConfig)
class AITranslationConfigAdmin(admin.ModelAdmin):
    list_display = ('domain', 'lang', 'provider', 'model', 'monthly_word_limit')
    search_fields = ('domain',)
