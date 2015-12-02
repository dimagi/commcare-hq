from corehq.apps.tour.models import StaticGuidedTour, GuidedTourStep
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop as _


SIMPLE_NEW_APP = StaticGuidedTour('simple_new_app', [
    GuidedTourStep(
        '#',
        _("Welcome to the App Builder"),
        _("Click 'Next' for a quick introduction to this page.")
    ),
    GuidedTourStep(
        '#',
        _("Edit a form"),
        _("Build and edit form questions and logic in our easy Form Builder.")
    ),
    GuidedTourStep(
        '#',
        _("Preview a form"),
        _("Check out what your form looks like in a web preview")
    ),
    GuidedTourStep(
        '#',
        _("Deploy your App"),
        _("Click here to install your app on a mobile device")
    ),
    GuidedTourStep(
        '#',
        _("Happy App Building!"),
        _(mark_safe("""For more advice, tutorials, and answers to your questions,
please checkout our <a href="http://help.commcarehq.org/">Help Site</a>."""))
    )
])
