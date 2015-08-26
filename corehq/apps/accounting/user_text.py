from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext_lazy as _
from corehq.apps.accounting.models import SoftwarePlanEdition as Edition, SoftwareProductType as Product, FeatureType

DESC_BY_EDITION = {
    Edition.COMMUNITY: {
        'name': _("Community"),
        'description': _("For projects in a pilot phase with a small group (up to 50) of "
                         "mobile users that only need very basic CommCare features."),
    },
    Edition.STANDARD: {
        'name': _("Standard"),
        'description': _("For projects with a medium set (up to 100) of mobile users that want to "
                         "build in limited SMS workflows and have increased data security needs."),
    },
    Edition.PRO: {
        'name': _("Pro"),
        'description': _("For projects with a large group (up to 500) of mobile users that want to "
                         "build in comprehensive SMS workflows and have increased reporting needs."),
    },
    Edition.ADVANCED: {
        'name': _("Advanced"),
        'description': _("For projects scaling to an even larger group (up to 1,000) of mobile users "
                         "that want the full CommCare feature set and dedicated support from Dimagi "
                         "staff.")
    },
    Edition.ENTERPRISE: {
        'name': _("Enterprise"),
        'description': _("For projects scaling regionally or country wide (1,001+ people) that require "
                         "the full CommCare feature set. Your organization will receive discounted "
                         "pricing and dedicated enterprise-level support from Dimagi.")
    }
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
        FeatureType.SMS: _("Monthly SMS"),
    }[feature_type]


class PricingTableCategories(object):
    CORE = 'core'
    MOBILE = 'mobile'
    WEB = 'web'
    ANALYTICS = 'analytics'
    SMS = 'sms'
    USER_MANAGEMENT_AND_SECURITY = 'user_management_security'
    SUPPORT = 'support'

    @classmethod
    def get_wiki_url(cls, category):
        return {
            cls.MOBILE: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-Mobile"),
            cls.WEB: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-Web"),
            cls.ANALYTICS: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-Analytics"),
            cls.SMS: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-SMS(CommConnect)"),
            cls.USER_MANAGEMENT_AND_SECURITY: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-UserManagementandSecurity"),
            cls.SUPPORT: _("https://wiki.commcarehq.org/display/commcarepublic/CommCare+Plan+Details#CommCarePlanDetails-Support"),
        }.get(category)
    
    @classmethod
    def get_title(cls, category, product):
        ensure_product(product)
        return {
            cls.MOBILE: _("Mobile"),
            cls.WEB: _("Web"),
            cls.ANALYTICS: _("Analytics"),
            cls.SMS: {
                Product.COMMCARE: _("SMS (CommConnect)"),
                Product.COMMCONNECT: _("SMS"),
                Product.COMMTRACK: _("SMS"),
            }[product],
            cls.USER_MANAGEMENT_AND_SECURITY: _("User Management and Security"),
            cls.SUPPORT: _("Support"),
        }.get(category)

    @classmethod
    def get_features(cls, category):
        f = PricingTableFeatures
        return {
            cls.CORE: (
                f.PRICING,
                f.MOBILE_LIMIT,
                f.ADDITIONAL_MOBILE_USER,
            ),
            cls.MOBILE: (
                f.JAVA_AND_ANDROID,
                f.MULTIMEDIA_SUPPORT,
            ),
            cls.WEB: (
                f.APP_BUILDER,
                f.EXCHANGE,
                f.API_ACCESS,
                f.LOOKUP_TABLES,
                f.WEB_APPS,
                f.CUSTOM_BRANDING,
            ),
            cls.ANALYTICS: (
                f.DATA_EXPORT,
                f.STANDARD_REPORTS,
                f.CROSS_PROJECT_REPORTS,
                f.CUSTOM_REPORTS,
                f.ADM,
            ),
            cls.SMS: (
                f.OUTBOUND_SMS,
                f.RULES_ENGINE,
                f.ANDROID_GATEWAY,
                f.SMS_DATA_COLLECTION,
                f.INBOUND_SMS,
                f.INCLUDED_SMS_DIMAGI,
                f.INCLUDED_SMS_CUSTOM,
            ),
            cls.USER_MANAGEMENT_AND_SECURITY: (
                f.USER_GROUPS,
                f.DATA_SECURITY_PRIVACY,
                f.ADVANCED_ROLES,
                f.BULK_CASE_USER_MANAGEMENT,
                f.HIPAA_COMPLIANCE,
                f.DE_ID_DATA,
            ),
            cls.SUPPORT: (
                f.COMMUNITY_SUPPORT,
                f.EMAIL_SUPPORT,
                f.APP_TROUBLESHOOTING,
                f.DEDICATED_SUPPORT_STAFF,
                f.DEDICATED_ACCOUNT_MANAGEMENT,
            ),
        }[category]


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
    CROSS_PROJECT_REPORTS = 'cross_project_reports'
    CUSTOM_REPORTS = 'custom_reports'
    ADM = 'adm'

    OUTBOUND_SMS = 'outbound_sms'
    RULES_ENGINE = 'rules_engine'
    ANDROID_GATEWAY = 'android_gateway'
    SMS_DATA_COLLECTION = 'sms_data_collection'
    INBOUND_SMS = 'inbound_sms'
    INCLUDED_SMS_DIMAGI = 'included_sms_dimagi'
    INCLUDED_SMS_CUSTOM = 'included_sms_custom'

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
            cls.CROSS_PROJECT_REPORTS: _("Cross-Project Reports"),
            cls.CUSTOM_REPORTS: _("Custom Reports Access"),
            cls.ADM: _('Active Data Management (<a href="http://www.commcarehq.org/tour/adm/">read more</a>)'),
            cls.OUTBOUND_SMS: _("Outbound Messaging"),
            cls.RULES_ENGINE: _("Rules Engine"),
            cls.ANDROID_GATEWAY: _("Android-based SMS Gateway"),
            cls.SMS_DATA_COLLECTION: _("SMS Data Collection"),
            cls.INBOUND_SMS: _("Inbound SMS (where available)"),
            cls.INCLUDED_SMS_DIMAGI: _("Free Messages (Dimagi Gateway)**"),
            cls.INCLUDED_SMS_CUSTOM: _("Messages (Your Gateway)"),
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
        return {
            cls.SOFTWARE_PLANS: (Edition.COMMUNITY, Edition.STANDARD, Edition.PRO, Edition.ADVANCED, Edition.ENTERPRISE),
            cls.PRICING: (_("Free"), _("$100 /month"), _("$500 /month"), _("$1,000 /month"), _('(<a href="http://www.dimagi.com/collaborate/contact-us/" target="_blank">Contact Us</a>)')),
            cls.MOBILE_LIMIT: (_("50"), _("100"), _("500"), _("1,000"), _("Unlimited / Discounted Pricing")),
            cls.ADDITIONAL_MOBILE_USER: (_("1 USD /month"), _("1 USD /month"), _("1 USD /month"), _("1 USD /month"), _("Unlimited / Discounted Pricing")),
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
            cls.CROSS_PROJECT_REPORTS: (False, True, True, True, True),
            cls.CUSTOM_REPORTS: (False, False, True, True, True),
            cls.ADM: (False, False, False, True, True),
            cls.OUTBOUND_SMS: (False, True, True, True, True),
            cls.RULES_ENGINE: (False, True, True, True, True),
            cls.ANDROID_GATEWAY: (False, True, True, True, True),
            cls.SMS_DATA_COLLECTION: (False, False, True, True, True),
            cls.INBOUND_SMS: (False, False, True, True, True),
            cls.INCLUDED_SMS_DIMAGI: (False, _("100 /month"), _("500 /month"), _("1,000 /month"), _("2,000 /month")),
            cls.INCLUDED_SMS_CUSTOM: (False, _("1 cent/SMS"), _("1 cent/SMS"), _("1 cent/SMS"), _("1 cent/SMS")),
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


class PricingTable(object):
    STRUCTURE_BY_PRODUCT = {
        Product.COMMCARE: (
            PricingTableCategories.CORE,
            PricingTableCategories.MOBILE,
            PricingTableCategories.WEB,
            PricingTableCategories.ANALYTICS,
            PricingTableCategories.SMS,
            PricingTableCategories.USER_MANAGEMENT_AND_SECURITY,
            PricingTableCategories.SUPPORT,
        ),
        Product.COMMCONNECT: (
            PricingTableCategories.CORE,
            PricingTableCategories.MOBILE,
            PricingTableCategories.WEB,
            PricingTableCategories.ANALYTICS,
            PricingTableCategories.SMS,
            PricingTableCategories.USER_MANAGEMENT_AND_SECURITY,
            PricingTableCategories.SUPPORT,
        ),
        Product.COMMTRACK: (
            PricingTableCategories.CORE,
            PricingTableCategories.MOBILE,
            PricingTableCategories.SMS,
            PricingTableCategories.WEB,
            PricingTableCategories.ANALYTICS,
            PricingTableCategories.USER_MANAGEMENT_AND_SECURITY,
            PricingTableCategories.SUPPORT,
        ),
    }
    VISIT_WIKI_TEXT = ugettext_noop("Visit the help site to learn more.")

    @classmethod
    def get_footer_by_product(cls, product, domain=None):
        ensure_product(product)
        from corehq.apps.domain.views import ProBonoStaticView
        return (
            ugettext_noop(
                mark_safe(
                    _('*Local taxes and other country-specific fees not included. Dimagi provides pro-bono '
                      'software plans on a needs basis. To learn more about this opportunity or see if your '
                      'program qualifies, please fill out our <a href="%(url)s">pro-bono form</a>.') % {
                          'url': (reverse('pro_bono', args=[domain]) if domain is
                                  not None else reverse(ProBonoStaticView.urlname)),
                      },
                )
            ),
            _("**Additional incoming and outgoing messages will be charged on a per-message fee, which "
              "depends on the telecommunications provider and country. Please note that this does not apply "
              "to the unlimited messages option, which falls under the category below."),
        )


    @classmethod
    def get_table_by_product(cls, product, domain=None):
        ensure_product(product)
        categories = cls.STRUCTURE_BY_PRODUCT[product]
        editions = PricingTableFeatures.get_columns(PricingTableFeatures.SOFTWARE_PLANS)
        edition_data = [(edition.lower(), DESC_BY_EDITION[edition]) for edition in editions]
        table_sections = []
        for category in categories:
            features = PricingTableCategories.get_features(category)
            feature_rows = []
            for feature in features:
                feature_rows.append({
                    'title': PricingTableFeatures.get_title(feature, product),
                    'columns': [(editions[ind].lower(), col) for ind, col in
                                enumerate(PricingTableFeatures.get_columns(feature))],
                })
            table_sections.append({
                'title': PricingTableCategories.get_title(category, product),
                'url': PricingTableCategories.get_wiki_url(category),
                'features': feature_rows,
                'category': category,
            })
        table = {
            'editions': edition_data,
            'title': PricingTableFeatures.get_title(PricingTableFeatures.SOFTWARE_PLANS, product),
            'sections': table_sections,
            'visit_wiki_text': cls.VISIT_WIKI_TEXT,
            'footer': cls.get_footer_by_product(product, domain=domain),
        }
        return table
