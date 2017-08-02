from __future__ import absolute_import
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext_lazy as _, ugettext
from corehq.apps.accounting.models import (
    FeatureType,
    SoftwarePlanEdition as Edition,
    SoftwareProductType as Product,
)

DESC_BY_EDITION = {
    Edition.COMMUNITY: {
        'name': _("Community"),
        'description': _("For projects in a pilot phase with a small group (up to %d) of "
                         "mobile users that only need very basic CommCare features."),
    },
    Edition.STANDARD: {
        'name': _("Standard"),
        'description': _("For projects with a medium set (up to %d) of mobile users that want to "
                         "build in limited SMS workflows and have increased data security needs."),
    },
    Edition.PRO: {
        'name': _("Pro"),
        'description': _("For projects with a large group (up to %d) of mobile users that want to "
                         "build in comprehensive SMS workflows and have increased reporting needs."),
    },
    Edition.ADVANCED: {
        'name': _("Advanced"),
        'description': _("For projects scaling to an even larger group (up to %d) of mobile users "
                         "that want the full CommCare feature set and dedicated support from Dimagi "
                         "staff.")
    },
    Edition.ENTERPRISE: {
        'name': _("Enterprise"),
        'description': _("For projects scaling regionally or country wide (1,001+ people) that require "
                         "the full CommCare feature set. Your organization will receive discounted "
                         "pricing and dedicated enterprise-level support from Dimagi.")
    },
    Edition.RESELLER: {
        'name': _("Reseller"),
        'description': _("Reseller")
    },
}

FEATURE_TYPE_TO_NAME = {
    FeatureType.SMS: _("SMS Messages"),
    FeatureType.USER: _("Mobile Workers"),
}


# This exists here specifically so that text can be translated
def ensure_product(product):
    if product not in [s[0] for s in Product.CHOICES]:
        raise ValueError("Unsupported Product")


def get_feature_name(feature_type, product):
    ensure_product(product)
    if feature_type not in [f[0] for f in FeatureType.CHOICES]:
        raise ValueError("Unsupported Feature")
    return {
        FeatureType.USER: {
            Product.COMMCARE: _("Mobile Users"),
            Product.COMMCONNECT: _("Mobile Users"),
            Product.COMMTRACK: _("Facilities"),
        }[product],
        FeatureType.SMS: _("SMS"),
    }[feature_type]


def get_feature_recurring_interval(feature_type):
    if feature_type == FeatureType.SMS:
        return _("Monthly")
    else:
        return None


class PricingTableFeatures(object):
    SOFTWARE_PLANS = 'software_plans'
    PRICING = 'pricing'
    MOBILE_LIMIT = 'mobile_limit'
    ADDITIONAL_MOBILE_USER = 'additional_mobile_user'
    JAVA_AND_ANDROID = 'java_and_android'
    MULTIMEDIA_SUPPORT = 'multimedia_support'

    APP_BUILDER = 'app_builder'
    EXCHANGE = 'exchange'
    API_ACCESS = 'api_access'
    LOOKUP_TABLES = 'lookup_tables'
    WEB_APPS = 'web_apps'
    CUSTOM_BRANDING = 'custom_branding'

    DATA_EXPORT = 'data_export'
    STANDARD_REPORTS = 'standard_reports'
    CUSTOM_REPORTS = 'custom_reports'
    ADM = 'adm'

    OUTBOUND_SMS = 'outbound_sms'
    RULES_ENGINE = 'rules_engine'
    ANDROID_GATEWAY = 'android_gateway'
    SMS_DATA_COLLECTION = 'sms_data_collection'
    INBOUND_SMS = 'inbound_sms'
    SMS_PRICING = 'sms_pricing'

    USER_GROUPS = 'user_groups'
    DATA_SECURITY_PRIVACY = 'data_security_privacy'
    ADVANCED_ROLES = 'advanced_roles'
    BULK_CASE_USER_MANAGEMENT = 'bulk_case_user_management'
    HIPAA_COMPLIANCE = 'hipaa_compliance'
    DE_ID_DATA = 'de_id_data'

    COMMUNITY_SUPPORT = 'community_support'
    EMAIL_SUPPORT = 'email_support'
    APP_TROUBLESHOOTING = 'app_troubleshooting'
    DEDICATED_SUPPORT_STAFF = 'dedicated_support_staff'
    DEDICATED_ACCOUNT_MANAGEMENT = 'dedicated_account_management'

    @classmethod
    def get_title(cls, feature, product):
        ensure_product(product)
        return {
            cls.SOFTWARE_PLANS: _("Software Plans"),
            cls.PRICING: _("Pricing*"),
            cls.MOBILE_LIMIT: {
                Product.COMMCARE: _("Mobile Users"),
                Product.COMMCONNECT: _("Mobile Users"),
                Product.COMMTRACK: _("Facilities")
            }[product],
            cls.ADDITIONAL_MOBILE_USER: {
                Product.COMMCARE: _("Price per Additional Mobile User"),
                Product.COMMCONNECT: _("Price per Additional Mobile User"),
                Product.COMMTRACK: _("Price per Additional Facility")
            }[product],
            cls.JAVA_AND_ANDROID: _("Java Feature Phones and Android Phones"),
            cls.MULTIMEDIA_SUPPORT: _("Multimedia Support"),
            cls.APP_BUILDER: {
                Product.COMMCARE: _('CommCare Application Builder'),
                Product.COMMCONNECT: _('CommCare Application Builder'),
                Product.COMMTRACK: _('CommCare Supply Application Builder'),
            }[product],
            cls.EXCHANGE: _('CommCare Exchange (<a href="http://www.commcarehq.org/exchange/">visit the exchange</a>)'),
            cls.API_ACCESS: _("API Access"),
            cls.LOOKUP_TABLES: _("Lookup Tables"),
            cls.WEB_APPS: _('Web-based Applications (<a href="https://confluence.dimagi.com/display/commcarepublic/CloudCare+-+Web+Data+Entry">CloudCare</a>)'),
            cls.CUSTOM_BRANDING: _("Custom Branding"),
            cls.DATA_EXPORT: _("Data Export"),
            cls.STANDARD_REPORTS: _("Standard Reports"),
            cls.CUSTOM_REPORTS: _("Custom Reports Access"),
            cls.ADM: _('Active Data Management (<a href="http://www.commcarehq.org/tour/adm/">read more</a>)'),
            cls.OUTBOUND_SMS: _("Outbound Messaging"),
            cls.RULES_ENGINE: _("Rules Engine"),
            cls.ANDROID_GATEWAY: _("Android-based SMS Gateway"),
            cls.SMS_DATA_COLLECTION: _("SMS Data Collection"),
            cls.INBOUND_SMS: _("Inbound SMS (where available)"),
            cls.SMS_PRICING: _("SMS Pricing"),
            cls.USER_GROUPS: _("User Groups"),
            cls.DATA_SECURITY_PRIVACY: _("Data Security and Privacy"),
            cls.ADVANCED_ROLES: _("Advanced Role-Based Access"),
            cls.BULK_CASE_USER_MANAGEMENT: _("Bulk Case and User Management"),
            cls.HIPAA_COMPLIANCE: _("HIPAA Compliance Assurance"),
            cls.DE_ID_DATA: _("De-identified Data"),
            cls.COMMUNITY_SUPPORT: {
                Product.COMMCARE: _('Community Support (<a href="https://groups.google.com/forum/?fromgroups#!forum/commcare-users">visit commcare-users</a>)'),
                Product.COMMCONNECT: _('Community Support (<a href="https://groups.google.com/forum/?fromgroups#!forum/commcare-users">visit commcare-users</a>)'),
                Product.COMMTRACK: _('Community Support (<a href="https://groups.google.com/forum/?fromgroups#!forum/commtrack-users">visit commtrack-users</a>)'),
            }[product],
            cls.EMAIL_SUPPORT: _("Direct Email Support"),
            cls.APP_TROUBLESHOOTING: _("Application Troubleshooting"),
            cls.DEDICATED_SUPPORT_STAFF: _("Dedicated Support Staff"),
            cls.DEDICATED_ACCOUNT_MANAGEMENT: _("Dedicated Enterprise Account Management"),
        }[feature]

    @classmethod
    def get_columns(cls, feature):
        from corehq.apps.domain.views import PublicSMSRatesView
        return {
            cls.SOFTWARE_PLANS: (Edition.COMMUNITY, Edition.STANDARD, Edition.PRO, Edition.ADVANCED, Edition.ENTERPRISE),
            cls.PRICING: (_("Free"), _("$100 /month"), _("$500 /month"), _("$1,000 /month"), _('(<a href="http://www.dimagi.com/collaborate/contact-us/" target="_blank">Contact Us</a>)')),
            cls.MOBILE_LIMIT: (_("10"), _("50"), _("250"), _("500"), _("Unlimited / Discounted Pricing")),
            cls.ADDITIONAL_MOBILE_USER: (_("2 USD /month"), _("2 USD /month"), _("2 USD /month"), _("2 USD /month"), _("Unlimited / Discounted Pricing")),
            cls.JAVA_AND_ANDROID: (True, True, True, True, True),
            cls.MULTIMEDIA_SUPPORT: (True, True, True, True, True),
            cls.APP_BUILDER: (True, True, True, True, True),
            cls.EXCHANGE: (True, True, True, True, True),
            cls.API_ACCESS: (False, True, True, True, True),
            cls.LOOKUP_TABLES: (False, True, True, True, True),
            cls.WEB_APPS: (False, False, True, True, True),
            cls.CUSTOM_BRANDING: (False, False, False, True, True),
            cls.DATA_EXPORT: (True, True, True, True, True),
            cls.STANDARD_REPORTS: (True, True, True, True, True),
            cls.CUSTOM_REPORTS: (False, False, True, True, True),
            cls.ADM: (False, False, False, True, True),
            cls.OUTBOUND_SMS: (False, True, True, True, True),
            cls.RULES_ENGINE: (False, True, True, True, True),
            cls.ANDROID_GATEWAY: (False, True, True, True, True),
            cls.SMS_DATA_COLLECTION: (False, False, True, True, True),
            cls.INBOUND_SMS: (False, False, True, True, True),
            cls.SMS_PRICING: (
                False,
            ) + (
                mark_safe('<a target="_blank" href="%(url)s">%(click_here)s</a>.' % {
                    'url': reverse(PublicSMSRatesView.urlname),
                    'click_here': ugettext('Click Here'),
                }),
            ) * 4,
            cls.USER_GROUPS: (True, True, True, True, True),
            cls.DATA_SECURITY_PRIVACY: (True, True, True, True, True),
            cls.ADVANCED_ROLES: (False, True, True, True, True),
            cls.BULK_CASE_USER_MANAGEMENT: (False, True, True, True, True),
            cls.DE_ID_DATA: (False, False, True, True, True),
            cls.HIPAA_COMPLIANCE: (False, False, False, True, True),
            cls.COMMUNITY_SUPPORT: (True, True, True, True, True),
            cls.EMAIL_SUPPORT: (False, True, True, True, True),
            cls.APP_TROUBLESHOOTING: (False, False, True, True, True),
            cls.DEDICATED_SUPPORT_STAFF: (False, False, False, True, True),
            cls.DEDICATED_ACCOUNT_MANAGEMENT: (False, False, False, False, True),
        }[feature]
