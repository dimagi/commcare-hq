from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    types = (
        ('info', 'info'),
        ('alert', 'alert'),
    )
    content = models.CharField(max_length=140)
    url = models.URLField()
    type = models.CharField(max_length=10, choices=types)
    created = models.DateTimeField(auto_now_add=True)
    users_read = models.ManyToManyField(User)


def get_notifications(user):
    notes = Notification.objects.all()
    read_notifications = Notification.objects.filter(users_read=user)

    def _fmt_note(note):
        note_dict = {
            'id': note.id,
            'url': note.url,
            'date': note.created.date(),
            'content': note.content,
            'type': note.type,
            'isRead': note in read_notifications
        }
        return note_dict

    return map(_fmt_note, notes)
