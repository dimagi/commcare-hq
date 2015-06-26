from dimagi.ext.couchdbkit import Document, StringProperty, DateTimeProperty, StringListProperty, BooleanProperty
from django.template.loader import render_to_string
from corehq.apps.announcements.crud import HQAnnouncementCRUDManager
from corehq.apps.crud.models import AdminCRUDDocumentMixin
from dimagi.utils.couch.cache import cache_core
from corehq.util import fix_urls
from dimagi.utils.couch.undo import DELETED_SUFFIX


class HQAnnouncement(Document, AdminCRUDDocumentMixin):
    """
        For global, site-wide HQ Announcements.
    """
    title = StringProperty()
    summary = StringProperty()
    highlighted_selectors = StringListProperty()
    date_created = DateTimeProperty()
    valid_until = DateTimeProperty()
    show_to_new_users = BooleanProperty(default=False)

    base_doc = "HQAnnouncement"

    _admin_crud_class = HQAnnouncementCRUDManager

    @property
    def as_html(self):
        return render_to_string("announcements/partials/base_announcement.html", {
            'title': self.title,
            'content': fix_urls(self.summary),
            'announcement_id': self._id,
        })


class ReportAnnouncement(HQAnnouncement):
    """
        Eventually this can have report-specific functionality. For now it's just a placeholder to differentiate from
        Global Announcements.
    """
    pass


class Notification(Document):
    """
    For handling persistent notifications that only disappear when the user explicitly dismisses them.

    Example Usage:
        class ExampleNotification(Notification):
            doc_type = 'ExampleNotification'

            def template(self):
                return 'example_notification.html'

        def example_page(request):
            ExampleNotification.display_if_needed(messages, request)
    """
    dismissed = BooleanProperty(default=False)
    user = StringProperty()
    base_doc = 'Notification'
    doc_type = 'Notification'

    def template(self):
        raise NotImplementedError

    @classmethod
    def get_notification(cls, username):
        notifications = cache_core.cached_view(
            cls.get_db(),
            "announcements/notifications",
            reduce=False,
            startkey=[cls._doc_type, username],
            endkey=[cls._doc_type, username, {}],
            include_docs=True,
            wrapper=cls.wrap)

        try:
            if len(notifications) > 1:
                for dup_notification in notifications[1:]:  # delete the duplicates
                    dup_notification.base_doc += DELETED_SUFFIX
                    dup_notification.save()
            notification = notifications[0]
        except IndexError:
            notification = None

        if not notification:
            notification = cls(user=username)
            notification.save()

        return notification

    @classmethod
    def unseen_notification(cls, username):
        notification = cls.get_notification(username)
        return notification if not notification.dismissed else None

    def render_notice(self, ctxt=None):
        ctxt = ctxt or {}
        ctxt.update({"note": self, "notification_template": self.template()})
        return render_to_string('announcements/partials/notification_wrapper.html', ctxt)

    @classmethod
    def display_if_needed(cls, messages, request, ctxt=None):
        note = cls.unseen_notification(request.couch_user.username)
        if note:
            ctxt = ctxt or {}
            messages.info(request, note.render_notice(ctxt=ctxt), extra_tags="html")
