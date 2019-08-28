from django.contrib import admin

from corehq.motech.utils import b64_aes_encrypt

from .forms import TransifexOrganizationForm
from .models import TransifexOrganization


class TransifexOrganizationAdmin(admin.ModelAdmin):
    form = TransifexOrganizationForm

    def save_model(self, request, obj, form, change):
        obj.api_token = b64_aes_encrypt(obj.api_token)
        super(TransifexOrganizationAdmin, self).save_model(request, obj, form, change)


admin.site.register(TransifexOrganization, TransifexOrganizationAdmin)
