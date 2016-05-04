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


def get_notifications():
    notes = Notification.objects.all()

    def _fmt_note(note):
        note_dict = {
            'id': note.id,
            'url': note.url,
            'date': note.created.date(),
            'content': note.content,
            'type': note.type,
            'isRead': False
        }
        return note_dict

    return map(_fmt_note, notes)
