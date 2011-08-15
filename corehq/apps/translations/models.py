from collections import defaultdict
from couchdbkit.ext.django.schema import Document, DictProperty
import commcare_translations
from dimagi.utils.couch.database import get_db

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
        

class Translation(object):
    @classmethod
    def get_translations(cls, lang, key=None, one=False):
        if key:
            translations = []
            r = get_db().view('translations/popularity',
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
            r = get_db().view('translations/popularity',
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
