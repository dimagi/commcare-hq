import collections
import datetime


FakeNotification = collections.namedtuple(
    'FakeNotification', ['isRead', 'content', 'url', 'date', 'type']
)


class NotificationType(object):
    INFO = 'info'
    ALERT = 'alert'


def get_fake_notifications():
    today = datetime.datetime.now()
    fake_notes = [
        FakeNotification(
            False,
            "CommCare 2.24 has been released!",
            "http://www.dimagi.com/blog/new-commcare-mobile-look-now-live/",
            today,
            NotificationType.INFO
        ),
        FakeNotification(
            False,
            "Interested in learning about emergency response?",
            "http://www.dimagi.com/blog/new-template-apps-free-8-"
            "week-online-app-building-course/",
            today,
            NotificationType.INFO
        ),
        FakeNotification(
            True,
            "Due to scheduled, necessary maintenance, our servers "
            "will be down periodically between 10/27 and 10/29. For"
            " more information, please read our blog.",
            "http://www.dimagi.com/blog/planned-commcarehq-downti"
            "me-for-maintenance/",
            today,
            NotificationType.ALERT
        ),
        FakeNotification(
            True,
            "We're excited to announce some new features "
            "in our monthly product update!  Check out our blog"
            " to learn more!",
            "http://www.dimagi.com/blog/octobers-commcare-update"
            "-new-data-cleaning-and-workforce-tracking-features/",
            today,
            NotificationType.INFO
        ),
        FakeNotification(
            True,
            "We've redesigned our exports feature!",
            "http://confluence.dimagi.com/",
            today,
            NotificationType.INFO
        ),
    ]

    def _fmt_note(fake_note):
        note_dict = fake_note._asdict()
        note_dict['date'] = '{dt:%B} {dt.day}, {dt.year}'.format(dt=fake_note.date)
        return note_dict

    return map(_fmt_note, fake_notes)
