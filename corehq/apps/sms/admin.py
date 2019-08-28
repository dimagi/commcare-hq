from django.contrib import admin
from corehq.apps.sms.models import QueuedSMS, SMS, PhoneBlacklist, PhoneNumber, SQLMobileBackendMapping


class SMSAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'date',
        'direction',
        'phone_number',
        'text',
        'backend_api',
        'processed',
        'error',
    ]

    search_fields = [
        'phone_number',
    ]

    ordering = ('-date',)


class QueuedSMSAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'date',
        'direction',
        'phone_number',
        'text',
        'backend_api',
        'processed',
        'error',
    ]

    search_fields = [
        'phone_number',
    ]

    ordering = ('-date',)


class PhoneBlacklistAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'phone_number',
        'send_sms',
        'can_opt_in',
    ]

    search_fields = [
        'phone_number',
    ]

    ordering = ('phone_number',)


class PhoneNumberAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'owner_doc_type',
        'owner_id',
        'phone_number',
        'is_two_way',
    ]

    search_fields = [
        'phone_number',
    ]

    ordering = ('phone_number',)


class SQLMobileBackendMappingAdmin(admin.ModelAdmin):

    list_display = [
        'is_global',
        'domain',
        'backend_type',
        'prefix',
        'backend',
    ]

    search_fields = [
        'domain',
    ]

    ordering = ('domain', 'prefix')


admin.site.register(SMS, SMSAdmin)
admin.site.register(QueuedSMS, QueuedSMSAdmin)
admin.site.register(PhoneBlacklist, PhoneBlacklistAdmin)
admin.site.register(PhoneNumber, PhoneNumberAdmin)
admin.site.register(SQLMobileBackendMapping, SQLMobileBackendMappingAdmin)
