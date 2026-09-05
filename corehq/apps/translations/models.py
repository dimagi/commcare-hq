from collections import defaultdict

from django.conf import settings
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


class AITranslation(models.Model):
    """Provenance: current state of each AI-translated app string.

    A string is AI-translated iff a row exists and the app's current
    value equals ``translated_value``; a differing value means the user
    edited it (detected lazily by diffing — no hooks in editing flows).
    ``string_key`` is anchored on module/form unique_ids rather than
    positional sheet names, so rows survive app restructuring.
    """
    STATUS_APPLIED = 'applied'
    STATUS_MANUALLY_EDITED = 'manually_edited'
    STATUS_CHOICES = [
        (STATUS_APPLIED, STATUS_APPLIED),
        (STATUS_MANUALLY_EDITED, STATUS_MANUALLY_EDITED),
    ]

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    lang = models.CharField(max_length=32)
    string_key = models.CharField(max_length=512)
    source_value = models.TextField()
    translated_value = models.TextField()
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('domain', 'app_id', 'lang', 'string_key')


class AITranslationUsage(models.Model):
    """Append-only event log, one row per translation run, for plan limits."""

    domain = models.CharField(max_length=255)
    app_id = models.CharField(max_length=255)
    lang = models.CharField(max_length=32)
    word_count = models.PositiveIntegerField()
    string_count = models.PositiveIntegerField()
    model = models.CharField(max_length=64)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # serves the monthly limit check: domain + created_on range
            models.Index(fields=['domain', 'created_on']),
        ]


class AITranslationConfig(models.Model):
    """Admin-editable per-domain AI translation overrides.

    Resolution order, per field: (domain, lang) > (domain,) >
    ``settings.AI_TRANSLATION_DEFAULTS``. Blank/None fields inherit
    from the less-specific level.
    """

    domain = models.CharField(max_length=255)
    lang = models.CharField(max_length=32, blank=True, default='')
    provider = models.CharField(max_length=32, blank=True, default='')
    model = models.CharField(max_length=64, blank=True, default='')
    monthly_word_limit = models.PositiveIntegerField(null=True, blank=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('domain', 'lang')

    @classmethod
    def resolve(cls, domain, lang):
        """Return the effective config for (domain, lang) as a dict
        with keys ``provider``, ``model`` and ``monthly_word_limit``.
        """
        resolved = dict(settings.AI_TRANSLATION_DEFAULTS)
        rows = {
            (row.domain, row.lang): row
            for row in cls.objects.filter(domain=domain, lang__in=['', lang])
        }
        for key in [(domain, ''), (domain, lang)]:
            row = rows.get(key)
            if row is None:
                continue
            for field in resolved:
                value = getattr(row, field)
                if value not in ('', None):
                    resolved[field] = value
        return resolved


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
