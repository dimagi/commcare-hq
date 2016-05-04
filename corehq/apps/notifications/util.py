from .models import Notification

def get_notifications_by_user(user, limit=10):
    notes = Notification.objects.all()[:limit]
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
