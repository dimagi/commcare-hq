from django.utils.translation import ugettext as _

from couchdbkit.exceptions import ResourceNotFound
from couchforms.analytics import get_form_analytics_metadata
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
    def __init__(self, form_doc, report, lang=None):
        self.form = form_doc
        self.report = report
        self.lang = lang

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
        return xmlns_to_name(
            self.report.domain,
            self.form.get("xmlns"),
            app_id=self.form.get("app_id"),
            lang=self.lang
        )

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
            form = get_form_analytics_metadata(domain, app_id, xmlns)
            try:
                self.app_id = form['app']['id'] if form else None
            except KeyError:
                self.app_id = None

    def get_label(self, lang=None):
        form = get_form_analytics_metadata(self.domain, self.app_id, self.xmlns)
        if form and form.get('app'):
            langs = form['app']['langs']
            app_name = form['app']['name']

            if form.get('is_user_registration'):
                form_name = "User Registration"
                title = "%s > %s" % (app_name, form_name)
            else:
                def _menu_name(menu, lang):
                    if lang and menu.get(lang):
                        return menu.get(lang)
                    else:
                        for lang in langs + menu.keys():
                            menu_name = menu.get(lang)
                            if menu_name is not None:
                                return menu_name
                        return "?"

                module_name = _menu_name(form["module"]["name"], lang)
                form_name = _menu_name(form["form"]["name"], lang)
                title = "%s > %s > %s" % (app_name, module_name, form_name)

            if form.get('app_deleted'):
                title += ' [Deleted]'
            if form.get('duplicate'):
                title += " [Multiple Forms]"
            name = title
        else:
            name = self.xmlns
        return name


def xmlns_to_name(domain, xmlns, app_id, lang=None):
    return _FormType(domain, xmlns, app_id).get_label(lang)
