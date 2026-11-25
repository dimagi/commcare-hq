from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.app_manager.models import Application
from corehq.apps.translations.app_translations.ai_panel import (
    get_last_ai_runs,
)
from corehq.apps.translations.models import AITranslationUsage

DOMAIN = 'test-domain'
APP_ID = 'test-app'
LATEST_BUILD_VERSION = 'corehq.apps.translations.app_translations.ai_panel.get_latest_build_version'


@patch(LATEST_BUILD_VERSION, return_value=None)
class TestGetLastAIRuns(TestCase):

    def test_latest_run_for_each_language(self, _):
        app = _make_app()
        _record_run('fra', strings_translated=5, created_on=datetime(2026, 9, 1))
        _record_run('fra', strings_translated=8, created_on=datetime(2026, 10, 1))
        _record_run('hin', strings_translated=3, created_on=datetime(2026, 9, 15))

        runs = get_last_ai_runs(app)

        assert runs.keys() == {'fra', 'hin'}
        assert runs['fra']['strings_translated'] == 8
        assert runs['fra']['created_on'] == '2026-10-01T00:00:00.000000Z'
        assert runs['hin']['strings_translated'] == 3

    def test_run_in_the_latest_build(self, latest_build_version):
        app = _make_app()
        latest_build_version.return_value = 7
        _record_run('fra', app_version=7)

        assert get_last_ai_runs(app)['fra']['in_version'] == 7

    def test_run_newer_than_the_latest_build(self, latest_build_version):
        app = _make_app()
        # a run saves the app, which bumps its version, so the run isn't
        # in a build until the user makes a new version
        latest_build_version.return_value = 6
        _record_run('fra', app_version=7)

        assert get_last_ai_runs(app)['fra']['in_version'] is None

    def test_app_without_builds(self, latest_build_version):
        app = _make_app()
        _record_run('fra', app_version=7)

        assert get_last_ai_runs(app)['fra']['in_version'] is None

    def test_runs_for_languages_the_app_no_longer_translates_are_ignored(self, _):
        # spa was removed from the app, and fra made its default language
        app = _make_app(langs=['fra', 'hin'])
        _record_run('spa')
        _record_run('fra')

        assert get_last_ai_runs(app) == {}

    def test_other_apps_runs_are_ignored(self, latest_build_version):
        app = _make_app()
        _record_run('fra', app_id='other-app')

        assert get_last_ai_runs(app) == {}
        assert not latest_build_version.called


def _make_app(langs=('en', 'fra', 'hin')):
    return Application(_id=APP_ID, domain=DOMAIN, langs=list(langs))


def _record_run(lang, app_id=APP_ID, strings_translated=1, app_version=1, created_on=None):
    run = AITranslationUsage.objects.create(
        domain=DOMAIN, app_id=app_id, lang=lang, strings_attempted=10,
        strings_translated=strings_translated, words_translated=1,
        total_app_strings=10, total_app_strings_ai_translated=1,
        app_version=app_version, model='m',
    )
    if created_on:
        # created_on is auto_now_add, so it can't be set on create
        AITranslationUsage.objects.filter(pk=run.pk).update(created_on=created_on)
