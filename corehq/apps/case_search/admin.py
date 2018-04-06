from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin

from corehq.apps.case_search.models import CaseSearchQueryAddition


class CaseSearchQueryAdditionAdmin(admin.ModelAdmin):
    list_display = ('domain', 'name', 'id')


admin.site.register(CaseSearchQueryAddition, CaseSearchQueryAdditionAdmin)
