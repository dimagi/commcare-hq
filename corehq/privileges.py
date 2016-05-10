from django.utils.translation import ugettext_lazy as _

LOOKUP_TABLES = 'lookup_tables'
API_ACCESS = 'api_access'

CLOUDCARE = 'cloudcare'

ACTIVE_DATA_MANAGEMENT = 'active_data_management'
CUSTOM_BRANDING = 'custom_branding'

CUSTOM_REPORTS = 'custom_reports'

# Legacy privilege associated with Pro plan
REPORT_BUILDER = 'user_configurable_report_builder'

# A la carte privileges that will be used in custom plans until "Add Ons" are
# added to the accounting system.
REPORT_BUILDER_TRIAL = 'report_builder_trial'
REPORT_BUILDER_5 = 'report_builder_5_reports'
REPORT_BUILDER_15 = 'report_builder_15_reports'
REPORT_BUILDER_30 = 'report_builder_30_reports'
REPORT_BUILDER_ADD_ON_PRIVS = {
    REPORT_BUILDER_TRIAL,
    REPORT_BUILDER_5,
    REPORT_BUILDER_15,
    REPORT_BUILDER_30,
}

ROLE_BASED_ACCESS = 'role_based_access'

OUTBOUND_SMS = 'outbound_sms'
REMINDERS_FRAMEWORK = 'reminders_framework'
CUSTOM_SMS_GATEWAY = 'custom_sms_gateway'
INBOUND_SMS = 'inbound_sms'

BULK_CASE_MANAGEMENT = 'bulk_case_management'
BULK_USER_MANAGEMENT = 'bulk_user_management'

DEIDENTIFIED_DATA = 'deidentified_data'

HIPAA_COMPLIANCE_ASSURANCE = 'hipaa_compliance_assurance'

ALLOW_EXCESS_USERS = 'allow_excess_users'

COMMCARE_LOGO_UPLOADER = 'commcare_logo_uploader'

LOCATIONS = 'locations'

USER_CASE = 'user_case'
DATA_CLEANUP = 'data_cleanup'  # bulk archive cases, edit submissions, auto update cases, etc.

TEMPLATED_INTENTS = 'templated_intents'
CUSTOM_INTENTS = 'custom_intents'

ADVANCED_DOMAIN_SECURITY = 'advanced_domain_security'

MAX_PRIVILEGES = [
    LOOKUP_TABLES,
    API_ACCESS,
    CLOUDCARE,
    ACTIVE_DATA_MANAGEMENT,
    CUSTOM_BRANDING,
    CUSTOM_REPORTS,
    ROLE_BASED_ACCESS,
    OUTBOUND_SMS,
    REMINDERS_FRAMEWORK,
    CUSTOM_SMS_GATEWAY,
    INBOUND_SMS,
    BULK_CASE_MANAGEMENT,
    BULK_USER_MANAGEMENT,
    DEIDENTIFIED_DATA,
    HIPAA_COMPLIANCE_ASSURANCE,
    ALLOW_EXCESS_USERS,
    COMMCARE_LOGO_UPLOADER,
    LOCATIONS,
    REPORT_BUILDER,
    REPORT_BUILDER_TRIAL,
    REPORT_BUILDER_5,
    REPORT_BUILDER_15,
    REPORT_BUILDER_30,
    USER_CASE,
    DATA_CLEANUP,
    TEMPLATED_INTENTS,
    CUSTOM_INTENTS,
]

# These are special privileges related to their own rates in a SoftwarePlanVersion
MOBILE_WORKER_CREATION = 'mobile_worker_creation'

# Other privileges related specifically to accounting processes
ACCOUNTING_ADMIN = 'accounting_admin'
OPERATIONS_TEAM = 'dimagi_ops'


class Titles(object):

    @classmethod
    def get_name_from_privilege(cls, privilege):
        return {
            LOOKUP_TABLES: _("Lookup Tables"),
            API_ACCESS: _("API Access"),
            CLOUDCARE: _("Web-Based Apps (CloudCare)"),
            ACTIVE_DATA_MANAGEMENT: _("Active Data Management"),
            CUSTOM_BRANDING: _("Custom Branding"),
            ROLE_BASED_ACCESS: _("Advanced Role-Based Access"),
            OUTBOUND_SMS: _("Outgoing Messaging"),
            INBOUND_SMS: _("Incoming Messaging"),
            REMINDERS_FRAMEWORK: _("Reminders Framework"),
            CUSTOM_SMS_GATEWAY: _("Custom Android Gateway"),
            BULK_CASE_MANAGEMENT: _("Bulk Case Management"),
            BULK_USER_MANAGEMENT: _("Bulk User Management"),
            ALLOW_EXCESS_USERS: _("Add Mobile Workers Above Limit"),
            DEIDENTIFIED_DATA: _("De-Identified Data"),
            HIPAA_COMPLIANCE_ASSURANCE: _("HIPAA Compliance Assurance"),
            COMMCARE_LOGO_UPLOADER: _("Custom CommCare Logo Uploader"),
            LOCATIONS: _("Locations"),
            REPORT_BUILDER: _('User Configurable Report Builder'),
            REPORT_BUILDER_TRIAL: _('Report Builder Trial'),
            REPORT_BUILDER_5: _('Report Builder, 5 report limit'),
            REPORT_BUILDER_15: _('Report Builder, 15 report limit'),
            REPORT_BUILDER_30: _('Report Builder, 30 report limit'),
            TEMPLATED_INTENTS: _('Built-in Integration'),
            CUSTOM_INTENTS: _('External Integration Framework'),
            DATA_CLEANUP: _('Data Management'),
            ADVANCED_DOMAIN_SECURITY: _('Domain Level Security Features')
        }.get(privilege, privilege)
