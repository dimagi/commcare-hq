from django.contrib import admin

from corehq.apps.data_interfaces.models import (
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

    search_fields = [
        'domain', 'case_type', 'status'
    ]

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


admin.site.register(DomainCaseRuleRun, DomainCaseRuleRunAdmin)
admin.site.register(CaseRuleSubmission, CaseRuleSubmissionAdmin)
