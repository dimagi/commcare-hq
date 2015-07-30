import json
from django.core.cache import cache
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch import get_cached_property, IncompatibleDocument, safe_index
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

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


class FormType(object):
    def __init__(self, domain, xmlns, app_id=None):
        self.domain = domain
        self.xmlns = xmlns
        if app_id:
            self.app_id = app_id
        else:
            try:
                form = FormType.forms_by_xmlns(domain, xmlns, app_id)
                self.app_id = form['app']['id']
            except Exception:
                self.app_id = {}

    def get_id_tuple(self):
        return self.domain, self.xmlns, self.app_id or None


    @property
    @memoized
    def metadata(self):
        try:
            return FormType.forms_by_xmlns(self.domain, self.xmlns, self.app_id)
        except Exception:
            return None

    def get_label(self, html=False, lang=None):
        if self.metadata:
            form = self.metadata
            if form.get('app'):
                langs = form['app']['langs']
                if lang:
                    langs = [lang] + langs
                app_name = form['app']['name']
                module_name = form_name = None
                if form.get('is_user_registration'):
                    form_name = "User Registration"
                    title = "%s > %s" % (app_name, form_name)
                else:
                    for lang in langs + form['module']['name'].keys():
                        module_name = form['module']['name'].get(lang)
                        if module_name is not None:
                            break
                    for lang in langs + form['form']['name'].keys():
                        form_name = form['form']['name'].get(lang)
                        if form_name is not None:
                            break
                    if module_name is None:
                        module_name = "?"
                    if form_name is None:
                        form_name = "?"
                    title = "%s > %s > %s" % (app_name, module_name, form_name)

                if form.get('app_deleted'):
                    title += ' [Deleted]'
                if form.get('duplicate'):
                    title += " [Multiple Forms]"

                if html:
                    name = u"<span>{title}</span>".format(title=title)
                else:
                    name = title
            else:
                name = self.xmlns
        else:
            name = self.xmlns
        return name

    @classmethod
    def forms_by_xmlns(cls, domain, xmlns, app_id):
        cache_key = 'corehq.apps.reports.display.FormType.forms_by_xmlns|{0}|{1}|{2}'.format(domain, xmlns, app_id)
        form_json = cache.get(cache_key)
        if form_json:
            form = json.loads(form_json)
        else:
            form = get_db().view('exports_forms/by_xmlns', key=[domain, app_id, xmlns], group=True).one()
            if form:
                form = form['value']
            # cache doc a short interval for the life of someone viewing the page
            cache.set(cache_key, json.dumps(form), 30)
        return form


def xmlns_to_name(domain, xmlns, app_id, html=False):
    return FormType(domain, xmlns, app_id).get_label(html=html)
