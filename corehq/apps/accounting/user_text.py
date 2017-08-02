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
