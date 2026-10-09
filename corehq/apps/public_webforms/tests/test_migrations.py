from importlib import import_module

from unmagic import use

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    delete_all_apps,
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.public_webforms.tests.utils import DOMAIN, create_webform

backfill_xmlns = import_module(
    'corehq.apps.public_webforms.migrations.0004_backfill_publicwebform_xmlns').backfill_xmlns


@use('db')
def test_backfill_reads_the_xmlns_from_the_pinned_build():
    factory = AppFactory(DOMAIN, name='Backfill App')
    __, form = factory.new_basic_module('survey', 'patient')
    form.source = get_simple_form(xmlns='http://example.com/survey')
    form.xmlns = 'http://example.com/survey'
    with patch_validate_xform():
        factory.app.save()
        build = factory.app.make_build()
        build.save()
    try:
        webform = create_webform(
            app_build_id=build.get_id, form_unique_id=form.unique_id, xmlns='', is_disabled=False)

        backfill_xmlns(PublicWebform)

        webform.refresh_from_db()
        assert webform.xmlns == 'http://example.com/survey'
        assert not webform.is_disabled
    finally:
        delete_all_apps()


@use('db')
def test_backfill_closes_a_webform_whose_build_is_gone():
    webform = create_webform(app_build_id='gone', xmlns='', is_disabled=False)

    backfill_xmlns(PublicWebform)

    webform.refresh_from_db()
    assert webform.xmlns == ''
    assert webform.is_disabled
