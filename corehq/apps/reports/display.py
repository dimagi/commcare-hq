from django.utils.translation import gettext as _
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from couchdbkit.exceptions import ResourceNotFound

from couchforms.analytics import get_form_analytics_metadata
from dimagi.utils.couch import IncompatibleDocument, get_cached_property
from dimagi.utils.couch.safe_index import safe_index

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS_MAP
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.util.dates import iso_string_to_datetime
from corehq.util.timezones.conversions import PhoneTime, ServerTime
from corehq.util.view_utils import absolute_reverse


ONE_WEEK = 7 * 24 * 60 * 60


class StringWithAttributes(str):

    def replace(self, *args):
        string = super(StringWithAttributes, self).replace(*args)
        return StringWithAttributes(string)


class FormDisplay:

    def __init__(self, form_doc, report, lang=None):
        self.form = form_doc
        self.report = report
        self.lang = lang

    @property
    def form_data_link(self):
        return format_html(
            "<a class='ajax_dialog' target='_new' href='{url}'>{text}</a>",
            url=absolute_reverse('render_form_data', args=[self.report.domain, self.form['_id']]),
            text=_("View Form")
        )

    @property
    def username(self):
        uid = self.form["form"]["meta"]["userID"]
        username = self.form["form"]["meta"].get("username")
        try:
            if username not in ['demo_user', 'admin']:
                full_name = get_cached_property(CouchUser, uid, 'full_name', expiry=ONE_WEEK)
                name = '"%s"' % full_name if full_name else ""
            else:
                name = ""
        except (ResourceNotFound, IncompatibleDocument):
            name = mark_safe('<b>[unregistered]</b>')  # nosec: no user input
        username = username or _('No data for username')
        if name:
            return format_html('{} {}', username, name)
        else:
            return username

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
            lang=self.lang,
            form_name=self.form.get("@name"),
        )


class _FormType(object):

    def __init__(self, domain, xmlns, app_id, form_name):
        self.domain = domain
        self.xmlns = xmlns
        self.app_id = app_id
        self.form_name = form_name

    def get_label(self, lang=None, separator=None):
        if separator is None:
            separator = " > "

        return (
            self.get_label_from_app(lang, separator)
            or self.get_name_from_xml(separator)
            or self.append_form_name(self.xmlns, separator)
        )

    def get_label_from_app(self, lang, separator):
        form = get_form_analytics_metadata(self.domain, self.app_id, self.xmlns)
        app = form and form.get('app')
        if not app:
            return

        langs = form['app']['langs']
        app_name = form['app']['name']

        if form.get('is_user_registration'):
            form_name = "User Registration"
            title = separator.join([app_name, form_name])
        else:
            def _menu_name(menu, lang):
                if lang and menu.get(lang):
                    return menu.get(lang)
                else:
                    for lang in langs + list(menu):
                        menu_name = menu.get(lang)
                        if menu_name is not None:
                            return menu_name
                    return "?"

            module_name = _menu_name(form["module"]["name"], lang)
            form_name = _menu_name(form["form"]["name"], lang)
            title = separator.join([app_name, module_name, form_name])

        if form.get('app_deleted'):
            title += ' [Deleted]'
        if form.get('duplicate'):
            title += " [Multiple Forms]"
        return title

    def get_name_from_xml(self, separator):
        if self.xmlns in SYSTEM_FORM_XMLNS_MAP:
            readable_xmlns = str(SYSTEM_FORM_XMLNS_MAP[self.xmlns])
            return self.append_form_name(readable_xmlns, separator)

    def append_form_name(self, name, separator):
        if self.form_name:
            name = separator.join([name, self.form_name])
        return name


def xmlns_to_name(domain, xmlns, app_id, lang=None, separator=None, form_name=None):
    return _FormType(domain, xmlns, app_id, form_name).get_label(lang, separator)


def xmlns_to_name_for_case_deletion(domain, form):
    """
    The difference between this function and the one above is that in the event that the form name
    can't be found, this function will attempt to recreate the standard 3 part structure, rather than
    defaulting to the xmlns url (form.xmlns). Currently only used in the case deletion workflow.

    TODO: Confirm it returning the form.xmlns isn't necessary + confirm this is the format we want to display
          for unknown form names in report tables and merge the two functions into one.
    """
    form_name = xmlns_to_name(domain, form.xmlns, form.app_id)
    if form_name == form.xmlns:
        extracted_name = [
            get_app(domain, form.app_id).name or "[Unknown App]",
            "[Unknown Module]",
            form.name or "[Unknown Form]"
        ]
        form_name = ' > '.join(extracted_name)
    return form_name
