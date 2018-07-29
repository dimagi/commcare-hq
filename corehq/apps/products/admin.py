from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import SQLProduct


class ProductAdmin(admin.ModelAdmin):
    model = SQLProduct

    list_display = [
        'domain',
        'name',
        'is_archived',
        'product_id'
    ]
    list_filter = [
        'domain',
        'is_archived',
    ]
    search_fields = [
        'name',
        'product_id'
    ]

admin.site.register(SQLProduct, ProductAdmin)
