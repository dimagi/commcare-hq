from corehq.apps.tour.models import GuidedTours


def activate_tour_for_user(tour_slug, user):
    GuidedTours.enable_tour_for_user(tour_slug, user.username)


def tour_is_enabled_for_user(tour_slug, user):
    return GuidedTours.is_tour_enabled_for_user(tour_slug, user)
