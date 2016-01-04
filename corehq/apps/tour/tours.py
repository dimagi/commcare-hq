from django.core.urlresolvers import reverse
from corehq.apps.tour.models import GuidedTour
from corehq.apps.tour.views import EndTourView


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


NEW_APP = StaticGuidedTour(
    'new_app', 'tour/config/new_app.html'
)
