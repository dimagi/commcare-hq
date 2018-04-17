from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import BlobExpiration


class BlobExpirationAdmin(admin.ModelAdmin):
    model = BlobExpiration
    list_display = (
        'bucket',
        'identifier',
        'created_on',
        'expires_on',
        'length',
        'deleted',
    )


admin.site.register(BlobExpiration, BlobExpirationAdmin)
