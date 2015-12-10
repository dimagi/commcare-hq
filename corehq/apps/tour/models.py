import datetime
from django.contrib.auth.models import User
from django.db import models
import json_field


class GuidedTours(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        unique=True
    )
    seen_tours = json_field.JSONField(
        default={},
    )

    @classmethod
    def has_seen_tour(cls, user, tour_slug):
        guided_tour, _ = GuidedTours.objects.get_or_create(user=user)
        return tour_slug not in guided_tour.seen_tours

    @classmethod
    def mark_as_seen(cls, user, tour_slug):
        guided_tour, _ = GuidedTours.objects.get_or_create(user=user)
        guided_tour.seen_tours[tour_slug] = datetime.datetime.now()
        guided_tour.save()


def mark_tour_as_seen_for_user(user, tour_slug):
    GuidedTours.mark_as_seen(user, tour_slug)


def has_user_seen_tour(user, tour_slug):
    return GuidedTours.has_seen_tour(user, tour_slug)
