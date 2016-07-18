from django.contrib.auth.models import User
from django.db import models


class GuidedTour(models.Model):
    user = models.ForeignKey(
        User,
        db_index=True,
    )
    tour_slug = models.CharField(
        max_length=255,
        db_index=True,
    )
    date_completed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'tour_slug')

    @classmethod
    def has_seen_tour(cls, user, tour_slug):
        return cls.objects.filter(user=user, tour_slug=tour_slug).count() > 0

    @classmethod
    def mark_as_seen(cls, user, tour_slug):
        cls.objects.get_or_create(user=user, tour_slug=tour_slug)
