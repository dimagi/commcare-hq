from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.contrib.postgres.fields import ArrayField
from six.moves import map


NOTIFICATION_TYPES = (
    ('billing', 'Billing Notification'),
    ('info', 'Product Notification'),
    ('alert', 'Maintenance Notification'),
)


class IllegalModelStateException(Exception):
    pass


class Notification(models.Model):
    content = models.CharField(max_length=140)
    url = models.URLField()
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    users_read = models.ManyToManyField(User)
    is_active = models.BooleanField(default=False)
    activated = models.DateTimeField(db_index=True, null=True, blank=True)
    domain_specific = models.BooleanField(default=False)
    domains = ArrayField(
        models.TextField(null=True, blank=True),
        null=True
    )

    class Meta(object):
        ordering = ["-activated"]

    @classmethod
    def get_by_user(cls, django_user, couch_user, limit=10):
        """Returns notifications for a particular user

        After five notifications all notifications should be marked as read.
        """
        notes = cls.objects.filter(Q(domain_specific=False) | Q(domains__overlap=couch_user.domains),
                                     is_active=True, activated__gt=django_user.date_joined)[:limit]
        read_notifications = set(cls.objects.filter(users_read=django_user).values_list('id', flat=True))

        def _fmt_note(note_idx):
            index = note_idx[0]
            note = note_idx[1]

            note_dict = {
                'id': note.id,
                'url': note.url,
                'date': '{dt:%B} {dt.day}'.format(dt=note.activated),
                'activated': note.activated,
                'content': note.content,
                'type': note.type,
                'isRead': (index > 4 or note.pk in read_notifications),
            }
            return note_dict

        return list(map(_fmt_note, enumerate(notes)))

    def mark_as_read(self, user):
        self.users_read.add(user)

    def set_as_last_seen(self, user):
        if not self.is_active:
            raise IllegalModelStateException("Only active notification can be marked as last seen")
        LastSeenNotification.objects.update_or_create(
            user=user,
            defaults={'last_seen_date': self.activated}
        )

    def activate(self):
        self.is_active = True
        self.activated = datetime.datetime.now()
        self.save()

    def deactivate(self):
        self.is_active = False
        self.activated = None
        self.save()


class LastSeenNotification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_seen_date = models.DateTimeField()

    @classmethod
    def get_last_seen_notification_date_for_user(cls, user):
        try:
            return LastSeenNotification.objects.get(user=user).last_seen_date
        except LastSeenNotification.DoesNotExist:
            return None


class DismissedUINotify(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    slug = models.CharField(max_length=140, db_index=True)
    date_dismissed = models.DateTimeField(auto_now_add=True)

    class Meta(object):
        unique_together = ('user', 'slug',)

    @classmethod
    def dismiss_notification(cls, user, slug):
        return DismissedUINotify.objects.update_or_create(
            user=user,
            slug=slug
        )

    @classmethod
    def is_notification_dismissed(cls, user, slug):
        return DismissedUINotify.objects.filter(user=user, slug=slug).exists()
