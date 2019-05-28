# coding=utf-8
from __future__ import absolute_import, unicode_literals

from testil import eq

from corehq.apps.app_manager import app_strings
from corehq.apps.app_manager.models import Application


def get_app():
    app = Application.new_app("test-domain", "Test App")
    app.langs = ["en", "rus"]
    app.set_translation("en", "hello", "Hello")
    app.set_translation("rus", "hello", "привет")
    app.set_translation("en", "goodbye", "Goodbye")
    app.set_translation("rus", "goodbye", "до свидания")
    app.set_translation("en", "all_yr_base", "ALL YOUR BASE ARE BELONG TO US")
    app.set_translation("rus", "all_yr_base", "ВСЯ ВАША БАЗА ОТНОСИТСЯ К НАМ")  # Well, that's what Google says
    return app


def test_get_app_translation_keys():
    app = get_app()
    select_known = app_strings.CHOICES["select-known"]
    keys = select_known.get_app_translation_keys(app)
    eq(keys, {"hello", "goodbye", "all_yr_base"})


def test_non_empty_only():
    things = {
        "none": None,
        "zero": 0,
        "empty": "",
        "empty_too": [],
        "also_empty": {},
        "all_of_the_things": [None, 0, "", [], {}],
    }
    non_empty_things = app_strings.non_empty_only(things)
    eq(non_empty_things, {"all_of_the_things": [None, 0, "", [], {}]})
