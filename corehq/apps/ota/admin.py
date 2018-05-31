from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import DemoUserRestore, MobileRecoveryMeasure


class DemoUserRestoreAdmin(admin.ModelAdmin):
    model = DemoUserRestore
    list_display = ['id', 'demo_user_id', 'timestamp_created', 'restore_blob_id']
    list_filter = ['demo_user_id']


class MobileRecoveryMeasureForm(forms.ModelForm):

    class Meta:
        model = MobileRecoveryMeasure
        fields = '__all__'

    def clean(self):
        data = self.cleaned_data

        for all_versions, version_min, version_max in [
            ('cc_all_versions', 'cc_version_min', 'cc_version_max'),
            ('app_all_versions', 'app_version_min', 'app_version_max'),
        ]:
            specifies_all_versions = data[all_versions]
            specifies_specific_versions = bool(data[version_min] or data[version_max])
            if specifies_all_versions == specifies_specific_versions:
                raise ValidationError("You must specify either {} or a range, but not both"
                                      .format(all_versions))
            if specifies_specific_versions and not (data[version_min] and data[version_max]):
                raise ValidationError("You must specify both {} and {}."
                                      .format(version_min, version_max))

        if data['cc_all_versions'] and data['app_all_versions']:
            raise ValidationError("You cannot apply a measure to all cc and app versions.")

        return self.cleaned_data


class MobileRecoveryMeasureAdmin(admin.ModelAdmin):
    list_display = ['measure', 'domain', 'app_id', 'sequence_number', 'created_on']
    list_filter = ['domain', 'app_id']
    form = MobileRecoveryMeasureForm
    readonly_fields = ['sequence_number', 'username']

    def save_model(self, request, obj, form, change):
        obj.username = request.user.username
        if not obj.sequence_number:
            obj.set_sequence_number()
        super(MobileRecoveryMeasureAdmin, self).save_model(request, obj, form, change)


admin.site.register(DemoUserRestore, DemoUserRestoreAdmin)
admin.site.register(MobileRecoveryMeasure, MobileRecoveryMeasureAdmin)
