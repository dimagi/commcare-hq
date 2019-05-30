from __future__ import absolute_import, unicode_literals

from collections import defaultdict

from django.contrib import admin
from django.db import models
from django.utils.functional import cached_property

from dimagi.ext.couchdbkit import (
    DictProperty,
    Document,
    ListProperty,
    StringProperty,
)
from dimagi.utils.couch import CouchDocLockableMixIn

from corehq.apps.app_manager.dbaccessors import get_app, get_app_ids_in_domain
from corehq.motech.utils import b64_aes_decrypt
from corehq.util.quickcache import quickcache


class TranslationMixin(Document):
    translations = DictProperty()

    def set_translation(self, lang, key, value):
        if lang not in self.translations:
            self.translations[lang] = {}
        if value is not None:
            self.translations[lang][key] = value
        else:
            del self.translations[lang][key]

    def set_translations(self, lang, translations):
        self.translations[lang] = translations


class StandaloneTranslationDoc(TranslationMixin, CouchDocLockableMixIn):
    """
    There is either 0 or 1 StandaloneTranslationDoc doc for each (domain, area).
    """
    domain = StringProperty()
    # For example, "sms"
    area = StringProperty()
    langs = ListProperty()

    @property
    def default_lang(self):
        if len(self.langs) > 0:
            return self.langs[0]
        else:
            return None

    @classmethod
    def get_obj(cls, domain, area, *args, **kwargs):
        return StandaloneTranslationDoc.view(
            "translations/standalone",
            key=[domain, area],
            include_docs=True
        ).one()

    @classmethod
    def create_obj(cls, domain, area, *args, **kwargs):
        obj = StandaloneTranslationDoc(
            domain=domain,
            area=area,
        )
        obj.save()
        return obj


class Translation(object):

    @classmethod
    def get_translations(cls, lang, key=None, one=False):
        from corehq.apps.app_manager.models import Application
        if key:
            translations = []
            r = Application.get_db().view('app_translations_by_popularity/view',
                startkey=[lang, key],
                endkey=[lang, key, {}],
                group=True
            ).all()
            r.sort(key=lambda x: -x['value'])
            for row in r:
                _, _, translation = row['key']
                translations.append(translation)
            if one:
                return translations[0] if translations else None
            return translations
        else:
            translations = defaultdict(list)
            r = Application.get_db().view('app_translations_by_popularity/view',
                startkey=[lang],
                endkey=[lang, {}],
                group=True
            ).all()
            r.sort(key=lambda x: (x['key'][1], -x['value']))
            for row in r:
                _, key, translation = row['key']
                translations[key].append(translation)
            if one:
                return dict([(key, val[0]) for key, val in translations.items()])
            else:
                return translations


FIELD_NAME_HELP = (
    'This is the same string that appears in the bulk app translation '
    "download in the module's sheet for case list or case detail under "
    '"property", or in the bulk ui translation download, also under '
    '"property". This could be an XPath, case property name, or UI '
    'property name. If it is an ID mapping then the property should be '
    "'&lt;property&gt; (ID Mapping Text)'. For ID mapping values each "
    "value should be '&lt;id mapping value&gt; (ID Mapping Value)'. "
    'Create a separate blacklist item for every property.'
    '<br>'
    'Example: Case detail for tasks_type could have separate entries for '
    'each of the following:'
    '<ul>'
    '    <li>tasks_type (ID Mapping Text)</li>'
    '    <li>child (ID Mapping Value)</li>'
    '    <li>pregnancy (ID Mapping Value)</li>'
    '</ul>'
)


class TransifexBlacklist(models.Model):
    """Used for removing case list and case detail translations before an upload to Transifex.

    Note that field_name is not sufficient to exclude properties as you can
    have two details in the same module that display the same information in a
    different way e.g. date of birth and age in years. display_text is used to
    determine which trnaslations to hold back from Transifex
    """

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    module_id = models.CharField(max_length=255, blank=True)
    field_type = models.CharField(
        max_length=100,
        choices=(
            ('detail', 'Case Detail'),
            ('list', 'Case List'),
            ('ui', 'UI'),
        )
    )
    field_name = models.TextField(help_text=FIELD_NAME_HELP)
    display_text = models.TextField(
        blank=True,
        help_text="The default language's translation for this detail/list. "
        "If display_text is not filled out then all translations that match "
        "the field_type and field_name will be blacklisted")

    def __str__(self):
        return "TransifexBlacklist(domain='{}', field_type='{}', field_name='{}')".format(
            self.domain,
            self.field_type,
            self.field_name,
        )
        # app and module omitted to avoid hitting database
        # app_id and module_id omitted because they are unfriendly

    @classmethod
    def translations_with_names(cls, domain):
        blacklisted = TransifexBlacklist.objects.filter(domain=domain).all().values()
        apps_modules_by_id = get_apps_modules_by_id(domain)
        ret = []
        for trans in blacklisted:
            r = trans.copy()
            app = apps_modules_by_id.get(trans['app_id'])
            module = app['modules'].get(trans['module_id']) if app else None
            r['app_name'] = app['name'] if app else trans['app_id']
            r['module_name'] = module['name'] if module else trans['module_id']
            ret.append(r)
        return ret


@quickcache(['domain'])
def get_apps_modules_by_id(domain):
    """
    Return a dictionary of {
        <app id>: {
            'name': <app name>,
            'modules': {
                <module id>: {'name': <module name>}
            }
        }
    }
    """
    apps = {}
    for app_id in get_app_ids_in_domain(domain):
        app = get_app(domain, app_id)
        modules = {}
        for module in app.get_modules():
            modules[module.unique_id] = {'name': module.default_name(app)}
        apps[app_id] = {
            'name': app.name,
            'modules': modules
        }
    return apps


class TransifexOrganization(models.Model):
    slug = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    api_token = models.CharField(max_length=255)

    def __str__(self):
        return self.name + ' (' + self.slug + ')'

    @cached_property
    def get_api_token(self):
        return b64_aes_decrypt(self.api_token)


class TransifexProject(models.Model):
    organization = models.ForeignKey(TransifexOrganization, on_delete=models.CASCADE)
    slug = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)

    def __str__(self):
        return self.name + ' (' + self.slug + ')'


admin.site.register(TransifexProject)
admin.site.register(TransifexBlacklist)
