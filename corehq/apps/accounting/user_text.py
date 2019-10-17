from django.utils.translation import ugettext_lazy as _

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

DESC_BY_EDITION = {
    SoftwarePlanEdition.COMMUNITY: {
        'name': _("Community"),
        'description': _("For projects in a pilot phase with a small group (up to %d) of "
                         "mobile users that only need very basic CommCare features."),
    },
    SoftwarePlanEdition.STANDARD: {
        'name': _("Standard"),
        'description': _("For projects with a medium set (up to %d) of mobile users that want to "
                         "build in limited SMS workflows and have increased data security needs."),
    },
    SoftwarePlanEdition.PRO: {
        'name': _("Pro"),
        'description': _("For projects with a large group (up to %d) of mobile users that want to "
                         "build in comprehensive SMS workflows and have increased reporting needs."),
    },
    SoftwarePlanEdition.ADVANCED: {
        'name': _("Advanced"),
        'description': _("For projects scaling to an even larger group (up to %d) of mobile users "
                         "that want the full CommCare feature set and dedicated support from Dimagi "
                         "staff.")
    },
    SoftwarePlanEdition.ENTERPRISE: {
        'name': _("Enterprise"),
        'description': _("For projects scaling regionally or country wide (1,001+ people) that require "
                         "the full CommCare feature set. Your organization will receive discounted "
                         "pricing and dedicated enterprise-level support from Dimagi.")
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
}


def get_feature_name(feature_type):
    if feature_type not in [f[0] for f in FeatureType.CHOICES]:
        raise ValueError("Unsupported Feature")
    return {
        FeatureType.USER: _("Mobile Users"),
        FeatureType.SMS: _("SMS"),
    }[feature_type]


def get_feature_recurring_interval(feature_type):
    if feature_type == FeatureType.SMS:
        return _("Monthly")
    else:
        return None
