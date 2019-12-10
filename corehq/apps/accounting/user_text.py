from django.utils.translation import ugettext_lazy as _

from corehq.apps.accounting.models import FeatureType, SoftwarePlanEdition

DESC_BY_EDITION = {
    SoftwarePlanEdition.COMMUNITY: {
        'name': _("Community"),
        'description': _("For projects in a pilot phase with a small group (up to {}) of "
                         "mobile users that only need very basic CommCare features."),
    },
    SoftwarePlanEdition.STANDARD: {
        'name': _("Standard"),
        'description': _("For programs with one-time data collection needs and "
                         "simple case management workflows, and for M&E teams "
                         "that need basic data tools like Excel-based "
                         "dashboards. ({} mobile workers included)"),
    },
    SoftwarePlanEdition.PRO: {
        'name': _("Pro"),
        'description': _("For programs with complex case management workflows "
                         "where field teams collaborate on tasks, and for M&E "
                         "teams that need to clean and report on their data. "
                         " ({} mobile workers included)"),
    },
    SoftwarePlanEdition.ADVANCED: {
        'name': _("Advanced"),
        'description': _("For programs with facility-based workflows and field "
                         "staff organized by location, as well as advanced "
                         "security needs. Also for M&E teams integrating "
                         "data capture with analytical tools like Power BI "
                         "and Tableau. ({} mobile workers included)")
    },
    SoftwarePlanEdition.ENTERPRISE: {
        'name': _("Enterprise"),
        'description': _("For organizations who want a sustainable path "
                         "towards improving last-mile mobile data collection "
                         "and service delivery practices across multiple "
                         "programs.")
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
