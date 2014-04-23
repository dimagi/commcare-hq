"""
Feature Previews are built on top of toggle, so if you migrate a toggle to
a feature preview, you shouldn't need to migrate the data, as long as the
slug is kept intact.
"""
from django.utils.translation import ugettext_lazy as _
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege

from . import privileges
from .toggles import StaticToggle, NAMESPACE_DOMAIN


class FeaturePreview(StaticToggle):
    """
    FeaturePreviews should be used in conjunction with normal role based access.
    Check the FeaturePreview first since that's a faster operation.

    e.g.

    if feature_previews.BETA_FEATURE.enabled(domain):
        try:
            ensure_request_has_privilege(request, privileges.BETA_FEATURE)
        except PermissionDenied:
            pass
        else:
            # do cool thing for BETA_FEATURE
    """
    def __init__(self, slug, label, description, privilege=None, help_link=None):
        self.description = description
        self.help_link = help_link
        self.privilege = privilege
        super(FeaturePreview, self).__init__(slug, label, namespaces=[NAMESPACE_DOMAIN])

    def has_privilege(self, request):
        if not self.privilege:
            return True

        try:
            ensure_request_has_privilege(request, self.privilege)
            return True
        except PermissionDenied:
            return False


SUBMIT_HISTORY_FILTERS = FeaturePreview(
    slug='submit_history_filters',
    label=_("Advanced Submit History Filters"),
    description=_("Filter the forms in the Submit History report by data in"
        "the form submissions. Add extra columns to the report that represent"
        "data in the forms."),
    # privilege=privileges.
    # help_link='https://confluence.dimagi.com/display/SPEC/Feature+Preiview+aka+Labs+Specification'
)

CALC_XPATHS = FeaturePreview(
    slug='calc_xpaths',
    label=_('Custom Calculations in Case List'),
    description=_("Specify a custom xpath expression to calculate a value"
        "in the case list or case detail screen."),
)
