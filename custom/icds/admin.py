from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import CCZHosting
from .forms import CCZHostingForm

from corehq.motech.utils import b64_aes_encrypt


class CCZHostingAdmin(admin.ModelAdmin):
    form = CCZHostingForm
    readonly_fields = ('identifier',)

    def save_model(self, request, obj, form, change):
        obj.password = b64_aes_encrypt(obj.password)
        super(CCZHostingAdmin, self).save_model(request, obj, form, change)


admin.site.register(CCZHosting, CCZHostingAdmin)
