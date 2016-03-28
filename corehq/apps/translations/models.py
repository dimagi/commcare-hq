from collections import defaultdict
from dimagi.ext.couchdbkit import (Document, DictProperty,
    StringProperty, ListProperty)
import commcare_translations
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

    
class TranslationDoc(TranslationMixin):
    @classmethod
    def create_from_txt(cls, lang, txt=None):
        """
        from corehq.apps.translations.models import *
        TranslationDoc.create_from_txt("pt")

        """
        if txt:
            dct = commcare_translations.loads(txt)
        else:
            dct = commcare_translations.load_translations(lang)
        t = cls(translations={lang: dct})
        t.save()
        return t
        

class StandaloneTranslationDoc(TranslationDoc, CouchDocLockableMixIn):
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
        if key:
            translations = []
            r = TranslationDoc.get_db().view('app_translations_by_popularity/view',
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
            r = TranslationDoc.get_db().view('app_translations_by_popularity/view',
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
