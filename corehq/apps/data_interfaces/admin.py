from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDuplicate,
    CaseRuleAction,
    CaseRuleSubmission,
    DomainCaseRuleRun,
)


class DomainCaseRuleRunAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'case_type',
        'started_on',
        'finished_on',
        'status',
        'cases_checked',
        'num_updates',
        'num_closes',
        'num_related_updates',
        'num_related_closes',
        'dbs_completed',
    ]

    search_fields = ['domain', 'case_type', 'status']

    ordering = ['-started_on']


class CaseRuleSubmissionAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'rule',
        'created_on',
        'form_id',
        'archived',
    ]

    search_fields = [
        'domain',
        'form_id',
    ]

    ordering = ['-created_on']


class CaseDuplicateAdmin(admin.ModelAdmin):
    model = CaseDuplicate
    search_fields = ['case_id']
    list_filter = ['action', 'case_id']


class CaseDeduplicationActionDefinitionAdmin(admin.ModelAdmin):
    model = CaseDeduplicationActionDefinition


class DeduplicationActionAdmin(admin.StackedInline):
    model = CaseRuleAction
    extra = 0
    fields = ['dedupe_action_link', 'duplicates']
    readonly_fields = ['dedupe_action_link', 'duplicates']

    def dedupe_action_link(self, obj):
        url = reverse("admin:data_interfaces_casededuplicationactiondefinition_change", args=[obj.definition.id])
        return format_html(f'<a href={url}>{str(obj.definition)}</a>')

    dedupe_action_link.short_description = "Deduplication Action"
    dedupe_action_link.allow_tags = True

    def duplicates(self, obj):
        duplicate_count = CaseDuplicate.objects.filter(action=obj.definition.id).count()
        url = reverse("admin:data_interfaces_caseduplicate_changelist") + f"?action__id__exact={obj.definition.id}"
        return format_html(f'<a href={url}>Duplicates count: ({duplicate_count})</a>')

    duplicates.short_description = "Duplicates"
    duplicates.allow_tags = True


class DeduplicationRuleAdmin(admin.ModelAdmin):
    inlines = [DeduplicationActionAdmin]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        return qs


admin.site.register(DomainCaseRuleRun, DomainCaseRuleRunAdmin)
admin.site.register(CaseRuleSubmission, CaseRuleSubmissionAdmin)
admin.site.register(AutomaticUpdateRule, DeduplicationRuleAdmin)
admin.site.register(CaseDeduplicationActionDefinition, CaseDeduplicationActionDefinitionAdmin)
admin.site.register(CaseDuplicate, CaseDuplicateAdmin)
