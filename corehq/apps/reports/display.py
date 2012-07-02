import json
from couchdbkit.exceptions import MultipleResultsFound, NoResultFound
from dimagi.utils.couch.database import get_db
from django.core.cache import cache
from django.core.urlresolvers import reverse

class StringWithAttributes(unicode):
    def replace(self, *args):
        string = super(StringWithAttributes, self).replace(*args)
        return StringWithAttributes(string)

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

    def get_label(self, html=False, lang=None):
        try:
            form = FormType.forms_by_xmlns(self.domain, self.xmlns, self.app_id)
        except Exception:
            name = self.xmlns
        else:
            if not form:
                name = self.xmlns
            elif form.get('app'):
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
                    name = u"<span>{title}</span>".format(
                        url=reverse("corehq.apps.app_manager.views.view_app", args=[self.domain, form['app']['id']])
                        + "?m=%s&f=%s" % (form['module']['id'], form['form']['id']),
                        title=title,
                        form=form_name
                    )
                else:
                    name = title
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
            form = get_db().view('reports/forms_by_xmlns', key=[domain, app_id, xmlns], group=True).one()
            if form:
                form = form['value']
            # only cache for 10 seconds
            cache.set(cache_key, json.dumps(form), 10)
        return form

def xmlns_to_name(domain, xmlns, app_id, html=False):
    return FormType(domain, xmlns, app_id).get_label(html=html)