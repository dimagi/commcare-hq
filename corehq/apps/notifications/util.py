from .models import Notification

def get_notifications_by_user(user, limit=10):
    notes = Notification.objects.filter(is_active=True)[:limit]
    read_notifications = Notification.objects.filter(users_read=user)

    def _fmt_note(note_idx):
        index = note_idx[0]
        note = note_idx[1]

        note_dict = {
            'id': note.id,
            'url': note.url,
            'date': '{dt:%B} {dt.day}'.format(dt=note.activated),
            'content': note.content,
            'type': note.type,
            'isRead': (index > 4 or note in read_notifications),
        }
        return note_dict

    return map(_fmt_note, enumerate(notes))
