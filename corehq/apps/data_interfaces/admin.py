from __future__ import absolute_import
from django.contrib import admin
from corehq.apps.data_interfaces.models import DomainCaseRuleRun, CaseRuleSubmission


class DomainCaseRuleRunAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'started_on',
        'finished_on',
        'status',
        'cases_checked',
        'num_updates',
        'num_closes',
        'num_related_updates',
        'num_related_closes',
    ]

    search_fields = [
        'domain',
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
    ]

    ordering = ['-created_on']


admin.site.register(DomainCaseRuleRun, DomainCaseRuleRunAdmin)
admin.site.register(CaseRuleSubmission, CaseRuleSubmissionAdmin)
