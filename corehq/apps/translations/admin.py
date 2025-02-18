from django.contrib import admin


from .forms import TransifexOrganizationForm
from .models import TransifexOrganization


class TransifexOrganizationAdmin(admin.ModelAdmin):
    form = TransifexOrganizationForm

    def save_model(self, request, obj, form, change):
        obj.plaintext_api_token = obj.api_token
        super(TransifexOrganizationAdmin, self).save_model(request, obj, form, change)


admin.site.register(TransifexOrganization, TransifexOrganizationAdmin)
