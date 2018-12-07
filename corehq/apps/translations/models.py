from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from django.contrib import admin
from django.db import models

from dimagi.ext.couchdbkit import (
    Document,
    DictProperty,
    ListProperty,
    StringProperty,
)
from dimagi.utils.couch import CouchDocLockableMixIn


class TranslationMixin(Document):
    translations = DictProperty()

    def init(self, lang):
        self.translations[lang] = Translation.get_translations(lang, one=True)

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


FIELD_NAME_HELP = """
Usually the string in either case list or detail under 'property'.
This could be an xpath or case property name.
If it is an ID Mapping then the property should be '<property> (ID Mapping Text)'.
For the values each value should be '<id mapping value> (ID Mapping Value)'.
Example: case detail for tasks_type would have entries:
    tasks_type (ID Mapping Text)
    child (ID Mapping Value)
    pregnancy (ID Mapping Value)
"""


class TransifexBlacklist(models.Model):
    """Used for removing case list and case detail translations before an
    upload to Transifex.

    This assumes that a default source translation is English exists.

    Note that field_name is not sufficient to exclude properties as you can
    have two details in the same module that display the same information in a
    different way e.g. date of birth and age in years. display_text is used to
    determine which trnaslations to hold back from Transifex
    """
    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=32)
    module_id = models.CharField(max_length=32)
    field_type = models.CharField(
        max_length=100,
        choices=(
            ('detail', 'Case Detail'),
            ('list', 'Case List'),
        )
    )
    field_name = models.TextField(help_text=FIELD_NAME_HELP)
    display_text = models.TextField(
        help_text="The default language's translation for this detail/list. "
        "If display_text is not filled out then all translations will be blacklisted")


admin.site.register(TransifexBlacklist)
