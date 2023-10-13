from django import forms
from django.contrib import admin

from corehq.apps.reports.models import TableauConnectedApp, TableauServer, TableauVisualization


admin.site.register(TableauServer)
admin.site.register(TableauVisualization)


# The encrypted field on the TableauConnectedApp model requires a custom admin form field.
class TableauConnectedAppAdminForm(forms.ModelForm):
    secret_value = forms.CharField(required=False,
                                   help_text="Field may be empty even if value has been provided.",
                                   widget=forms.PasswordInput)

    def save(self, commit=True):
        unencrypted_secret_value = self.cleaned_data.get('secret_value', None)
        instance = super(TableauConnectedAppAdminForm, self).save(commit=commit)
        if unencrypted_secret_value:
            # Call this special setter method when saving the form to encrypt the value.
            instance.plaintext_secret_value = unencrypted_secret_value
            if commit:
                instance.save()
        return instance


class TableauConnectedAppAdmin(admin.ModelAdmin):
    # This set of field excludes encrypted_secret_value, replacing it with the custom secret_value field.
    fields = ('app_client_id', 'server', 'secret_id', 'secret_value',)

    form = TableauConnectedAppAdminForm


admin.site.register(TableauConnectedApp, TableauConnectedAppAdmin)
