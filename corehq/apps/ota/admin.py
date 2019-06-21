from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import DemoUserRestore, MobileRecoveryMeasure
from .views import get_recovery_measures_cached


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

        application_measures = ['app_reinstall_and_update', 'app_offline_reinstall_and_update', 'app_update']
        commcare_measures = ['cc_reinstall', 'cc_update']
        if data['measure'] in application_measures:
            if data['app_all_versions']:
                raise ValidationError("App related measures must specify an app version range")
        elif data['measure'] in commcare_measures:
            if data['cc_all_versions']:
                raise ValidationError("Commcare related measures must specify a commcare version range")
        else:
            raise AssertionError(
                "This measure doesn't have any specific validation defined, you must code in "
                "validation for all possible measures (even if it's just to explicitly mark that "
                "no further validation is necessary)."
            )

        return self.cleaned_data


class MobileRecoveryMeasureAdmin(admin.ModelAdmin):
    list_display = ['measure', 'domain', 'app_id', 'sequence_number', 'created_on']
    list_filter = ['domain', 'app_id']
    form = MobileRecoveryMeasureForm
    readonly_fields = ['sequence_number', 'username']

    def save_model(self, request, obj, form, change):
        obj.username = request.user.username
        super(MobileRecoveryMeasureAdmin, self).save_model(request, obj, form, change)
        get_recovery_measures_cached.clear(obj.domain, obj.app_id)


admin.site.register(DemoUserRestore, DemoUserRestoreAdmin)
admin.site.register(MobileRecoveryMeasure, MobileRecoveryMeasureAdmin)
