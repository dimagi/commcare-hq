from django.utils.translation import gettext_lazy as _

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import prelogin_url

DESC_BY_EDITION = {
    SoftwarePlanEdition.FREE: {
        'name': _("Free"),
        'description': _(
            "Designed for practice purposes and not intended for live projects. Upgrade to access "
            "full features and more users. Learn about "
        ) + f'<a href="{prelogin_url("public_pricing")}" target="_blank">' + _("CommCare plans") + '</a>.',
    },
    SoftwarePlanEdition.STANDARD: {
        'name': _("Standard"),
        'description': _("Get started. Build secure apps for offline mobile data collection and case management. "
                         "{} users included."),
    },
    SoftwarePlanEdition.PRO: {
        'name': _("Pro"),
        'description': _("Beyond the basics. Unlock reporting, case sharing, and hands-on support. "
                         "{} users included."),
    },
    SoftwarePlanEdition.ADVANCED: {
        'name': _("Advanced"),
        'description': _("Unlock everything. Our most secure plan, built for managing connected systems across "
                         "locations and user profiles, featuring web apps, advanced security, and robust admin "
                         "and data management tools. "
                         "{} users included.")
    },
    SoftwarePlanEdition.ENTERPRISE: {
        'name': _("Enterprise"),
        'description': _("For organizations that need a sustainable path to "
                         "scale mobile data collection and service delivery "
                         "across multiple teams, programs, or countries.")
    },
    SoftwarePlanEdition.PAUSED: {
        'name': _("Paused"),
        'description': _("Paused"),
    },
    SoftwarePlanEdition.RESELLER: {
        'name': _("Reseller"),
        'description': _("Reseller")
    },
    SoftwarePlanEdition.MANAGED_HOSTING: {
        'name': _("Managed Hosting"),
        'description': _("Managed Hosting"),
    }
}

FEATURE_TYPE_TO_NAME = {
    FeatureType.SMS: _("SMS Messages"),
    FeatureType.USER: _("Mobile Workers"),
    FeatureType.WEB_USER: _("Web Users"),
    FeatureType.FORM_SUBMITTING_MOBILE_WORKER: _("Form-Submitting Mobile Workers"),
}


def get_feature_name(feature_type):
    if feature_type not in [f[0] for f in FeatureType.CHOICES]:
        raise ValueError("Unsupported Feature")
    return FEATURE_TYPE_TO_NAME[feature_type]


def get_feature_recurring_interval(feature_type):
    if feature_type == FeatureType.SMS:
        return _("Monthly")
    else:
        return None
