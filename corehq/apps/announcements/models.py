import re
from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, StringListProperty, BooleanProperty
from django.template.loader import render_to_string
from corehq.apps.announcements.crud import HQAnnouncementCRUDManager
from corehq.apps.crud.models import AdminCRUDDocumentMixin
from dimagi.utils.decorators.memoized import memoized


def fix_urls(text):
    """
    Wraps urls in a string with anchor tags
    http://stackoverflow.com/questions/1071191/detect-urls-in-a-string-and-wrap-with-a-href-tag#answer-1071240
    """
    pat_url = re.compile(  r'''
                     (?x)( # verbose identify URLs within text
         (http|ftp|gopher) # make sure we find a resource type
                       :// # ...needs to be followed by colon-slash-slash
            (\w+[:.]?){2,} # at least two domain groups, e.g. (gnosis.)(cx)
                      (/?| # could be just the domain name (maybe w/ slash)
                [^ \n\r"]+ # or stuff then space, newline, tab, quote
                    [\w/]) # resource name ends in alphanumeric or slash
         (?=[\s\.,>)'"\]]) # assert: followed by white or clause ending
                         ) # end of match group
                           ''')
    pat_email = re.compile(r'''
                    (?xm)  # verbose identify URLs in text (and multiline)
                 (?=^.{11} # Mail header matcher
         (?<!Message-ID:|  # rule out Message-ID's as best possible
             In-Reply-To)) # ...and also In-Reply-To
                    (.*?)( # must grab to email to allow prior lookbehind
        ([A-Za-z0-9-]+\.)? # maybe an initial part: DAVID.mertz@gnosis.cx
             [A-Za-z0-9-]+ # definitely some local user: MERTZ@gnosis.cx
                         @ # ...needs an at sign in the middle
              (\w+\.?){2,} # at least two domain groups, e.g. (gnosis.)(cx)
         (?=[\s\.,>)'"\]]) # assert: followed by white or clause ending
                         ) # end of match group
                           ''')

    for url in re.findall(pat_url, text):
       text = text.replace(url[0], '<a href="%(url)s">%(url)s</a>' % {"url" : url[0]})

    for email in re.findall(pat_email, text):
       text = text.replace(email[1], '<a href="mailto:%(email)s">%(email)s</a>' % {"email" : email[1]})

    return text


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
    # @memoized todo: figure out how to reset cache of class methods
    def get_notification(cls, username):
        notification = cls.view("announcements/notifications",
            reduce=False,
            startkey=[cls._doc_type, username],
            endkey=[cls._doc_type, username, {}],
            include_docs=True,
        ).one()

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
