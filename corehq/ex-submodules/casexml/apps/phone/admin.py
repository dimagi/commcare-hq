from django.contrib import admin
from .models import *


class OwnershipCleanlinessAdmin(admin.ModelAdmin):

    model = OwnershipCleanliness
    list_display = [
        'domain',
        'owner_id',
        'is_clean',
        'last_checked',
        'hint',
    ]

    search_fields = [
        'domain',
        'owner_id',
    ]

    list_filter = [
        'is_clean',
    ]


admin.site.register(OwnershipCleanliness, OwnershipCleanlinessAdmin)
