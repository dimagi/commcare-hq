from collections import defaultdict

from django.db import models


class SMSTranslations(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    langs = models.JSONField(default=list)
    translations = models.JSONField(default=dict)

    @property
    def default_lang(self):
        return self.langs[0] if self.langs else None

    def set_translations(self, lang, translations):
        self.translations[lang] = translations


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
