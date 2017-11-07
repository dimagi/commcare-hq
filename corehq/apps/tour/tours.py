from __future__ import absolute_import
from corehq.apps.tour.models import GuidedTour
from corehq.apps.tour.views import EndTourView
from corehq.util import reverse


def _implies(p, q):
    """
    Logical implication operator
    Return p => q
    """
    return (not p) or q


class StaticGuidedTour(object):

    def __init__(self, slug, template):
        self.slug = slug
        self.template = template

    def get_tour_data(self):
        return {
            'slug': self.slug,
            'template': self.template,
            'endUrl': reverse(EndTourView.urlname, args=(self.slug,)),
        }

    def is_enabled(self, user):
        return not GuidedTour.has_seen_tour(user, self.slug)
