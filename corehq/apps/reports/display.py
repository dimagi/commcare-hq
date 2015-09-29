from django.utils.translation import ugettext as _
from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.reports.analytics import get_form_app_info
from dimagi.utils.couch import get_cached_property, IncompatibleDocument, safe_index
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.conversions import ServerTime, PhoneTime
from corehq.util.view_utils import absolute_reverse


class StringWithAttributes(unicode):
    def replace(self, *args):
        string = super(StringWithAttributes, self).replace(*args)
        return StringWithAttributes(string)


class FormDisplay(object):
    def __init__(self, form_doc, report):
        self.form = form_doc
        self.report = report

    @property
    def form_data_link(self):
        return "<a class='ajax_dialog' target='_new' href='%(url)s'>%(text)s</a>" % {
            "url": absolute_reverse('render_form_data', args=[self.report.domain, self.form['_id']]),
            "text": _("View Form")
        }

    @property
    def username(self):
        uid = self.form["form"]["meta"]["userID"]
        username = self.form["form"]["meta"].get("username")
        try:
            if username not in ['demo_user', 'admin']:
                full_name = get_cached_property(CouchUser, uid, 'full_name', expiry=7*24*60*60)
                name = '"%s"' % full_name if full_name else ""
            else:
                name = ""
        except (ResourceNotFound, IncompatibleDocument):
            name = "<b>[unregistered]</b>"
        return (username or _('No data for username')) + (" %s" % name if name else "")

    @property
    def submission_or_completion_time(self):
        time = iso_string_to_datetime(safe_index(self.form, self.report.time_field.split('.')))
        if self.report.by_submission_time:
            user_time = ServerTime(time).user_time(self.report.timezone)
        else:
            user_time = PhoneTime(time, self.report.timezone).user_time(self.report.timezone)
        return user_time.ui_string(USER_DATETIME_FORMAT_WITH_SEC)

    @property
    def readable_form_name(self):
        return xmlns_to_name(self.report.domain, self.form.get("xmlns"), app_id=self.form.get("app_id"))

    @property
    def other_columns(self):
        return [self.form["form"].get(field) for field in self.report.other_fields]


class _FormType(object):
    def __init__(self, domain, xmlns, app_id=None):
        self.domain = domain
        self.xmlns = xmlns
        if app_id:
            self.app_id = app_id
        else:
            try:
                form_app_info = get_form_app_info(domain, xmlns, app_id)
                self.app_id = form_app_info.app_id
            except Exception:
                self.app_id = {}

    def get_label(self, html=False):
        info = get_form_app_info(self.domain, self.xmlns, self.app_id)
        if info and info.app_id:
            langs = info.app_langs
            app_name = info.app_name
            if info.is_user_registration:
                title = "{} > User Registration".format(app_name)
            else:
                module_name = _translate(info.module_name, langs) or '?'
                form_name = _translate(info.form_name, langs) or '?'
                title = "{} > {} > {}".format(app_name, module_name, form_name)

            if info.app_deleted:
                title += ' [Deleted]'
            if info.duplicate:
                title += " [Multiple Forms]"

            if html:
                name = u"<span>{title}</span>".format(title=title)
            else:
                name = title
        else:
            name = self.xmlns
        return name


def _translate(translations, langs):
    for lang in langs + translations.keys():
        module_name = translations.get(lang)
        if module_name is not None:
            return module_name


def xmlns_to_name(domain, xmlns, app_id, html=False):
    return _FormType(domain, xmlns, app_id).get_label(html=html)
