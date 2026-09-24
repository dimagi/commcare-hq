from types import SimpleNamespace

import pytest
from unmagic import fixture, use

from corehq.apps.app_manager.dbaccessors import get_app, get_latest_build_id
from corehq.apps.app_manager.models import Application, ReportAppConfig
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    delete_all_apps,
    get_simple_form,
    patch_validate_xform,
)
from corehq.apps.domain.models import Domain
from corehq.apps.public_webforms.app_builds import (
    _restrict_reports_to_form,
    create_public_webform_build,
    delete_public_webform_build,
)
from corehq.apps.hqmedia.models import HQMediaMapItem
from corehq.blobs import get_blob_db

DOMAIN = 'public-webform-endpoints'
TARGET_MEDIA = 'jr://file/commcare/image/target.png'
OTHER_MEDIA = 'jr://file/commcare/image/other.png'


def _form_source_referencing(*instance_names):
    refs = ', '.join(f"instance('{name}')/rows" for name in instance_names)
    return get_simple_form(xmlns='target-form').replace(
        '<bind nodeset="/data/question1" type="xsd:string" />',
        f'<bind nodeset="/data/question1" type="xsd:string" calculate="concat({refs})" />',
    )


@pytest.mark.parametrize('instance_name, expected', [
    ('commcare-reports:used', ['used']),
    ('commcare-reports-filters:used', ['used']),
    ('casedb', []),
], ids=['report', 'report-filter', 'unrelated-instance'])
def test_restrict_reports_to_form_keeps_only_what_the_form_references(
    instance_name, expected
):
    factory = AppFactory(DOMAIN, build_version='2.51.0')
    __, form = factory.new_basic_module('survey', 'patient')
    form.source = _form_source_referencing(instance_name)
    report_module = factory.new_report_module('reports')
    report_module.report_configs = [
        ReportAppConfig(report_id='report-1', report_slug='used'),
        ReportAppConfig(report_id='report-2', report_slug='unused'),
    ]

    _restrict_reports_to_form(factory.app, form.unique_id)

    assert [c.report_slug for c in report_module.report_configs] == expected


@use('db')
@fixture
def released_app():
    """A released build of an app with two forms, each with its own icon and a profile.
    """
    domain_obj = Domain.get_or_create_with_name(DOMAIN)
    # session endpoints require CommCare 2.51+ (feature_support)
    factory = AppFactory(DOMAIN, name='PWF App', build_version='2.51.0')
    __, form = factory.new_basic_module('survey', 'patient')
    form.source = get_simple_form(xmlns=form.unique_id)
    form.set_icon('en', TARGET_MEDIA)
    __, other_form = factory.new_basic_module('other', 'patient')
    other_form.source = get_simple_form(xmlns=other_form.unique_id)
    other_form.set_icon('en', OTHER_MEDIA)
    try:
        with patch_validate_xform():
            app = factory.app
            app.profile = {
                'properties': {'cc-autoup-freq': 'freq-never'},
                'custom_properties': {'cc-internal-thing': 'do not publish'},
            }
            app.multimedia_map = {
                path: HQMediaMapItem(
                    multimedia_id=f'{name}-media-id',
                    media_type='CommCareImage',
                    version=1,
                )
                for name, path in [('target', TARGET_MEDIA), ('other', OTHER_MEDIA)]
            }
            app.save()
            build = app.make_build()
            build.is_released = True
            build.save()
            yield SimpleNamespace(
                domain=DOMAIN,
                app_id=app.get_id,
                build_id=build.get_id,
                form_unique_id=form.unique_id,
            )
    finally:
        delete_all_apps()
        domain_obj.delete()


@use(released_app)
class TestCreatePublicWebformBuild:

    def test_generates_detached_build_emitting_the_endpoint(self):
        app = released_app()
        build_id, endpoint_id = create_public_webform_build(
            app.domain, app.app_id, app.form_unique_id)

        assert build_id != app.build_id
        new_build = get_app(app.domain, build_id)
        # detached from the app's lineage, but traceable back to it
        assert new_build.copy_of == f'{app.app_id}__public_webform'
        suite = new_build.fetch_attachment('files/suite.xml')
        suite = suite.decode('utf-8')
        assert endpoint_id in suite

    def test_canonical_is_never_written(self):
        app = released_app()
        version_before = get_app(app.domain, app.app_id).version
        create_public_webform_build(app.domain, app.app_id, app.form_unique_id)
        canonical = get_app(app.domain, app.app_id)
        assert canonical.version == version_before
        assert canonical.get_form(app.form_unique_id).session_endpoint_id is None

    def test_detached_build_stays_out_of_the_lineage(self):
        app = released_app()
        create_public_webform_build(app.domain, app.app_id, app.form_unique_id)
        # the generated build must not become the app's latest build
        assert get_latest_build_id(app.domain, app.app_id) == app.build_id

    def test_always_generates_an_endpoint(self):
        """Reusing an endpoint would pin a build a user can delete."""
        app = released_app()
        released = get_app(app.domain, app.build_id)
        released.get_form(app.form_unique_id).session_endpoint_id = 'existing-endpoint'
        released.save(increment_version=False)
        assert get_app(app.domain, app.build_id).get_form(
            app.form_unique_id).session_endpoint_id == 'existing-endpoint'

        build_id, endpoint_id = create_public_webform_build(
            app.domain, app.app_id, app.form_unique_id)

        assert build_id != app.build_id
        assert endpoint_id != 'existing-endpoint'

    def test_maps_only_the_media_its_form_uses(self):
        app = released_app()

        build_id, __ = create_public_webform_build(
            app.domain, app.app_id, app.form_unique_id)

        build = get_app(app.domain, build_id)
        assert set(build.multimedia_map) == {TARGET_MEDIA}

    def test_drops_the_projects_custom_properties(self):
        app = released_app()

        build_id, __ = create_public_webform_build(
            app.domain, app.app_id, app.form_unique_id)

        build = get_app(app.domain, build_id)
        assert 'custom_properties' not in build.profile


@use(released_app)
class TestDeletePublicWebformBuild:

    def test_deletes_the_build_doc_and_its_build_files(self):
        app = released_app()
        build_id, __ = create_public_webform_build(
            app.domain, app.app_id, app.form_unique_id)
        assert get_blob_db().metadb.get_for_parent(build_id)

        delete_public_webform_build(app.domain, build_id)

        # a hard delete: no soft-deleted doc, no orphaned build files
        assert not Application.get_db().doc_exist(build_id)
        assert get_blob_db().metadb.get_for_parent(build_id) == []

    def test_leaves_a_build_it_did_not_generate_alone(self):
        app = released_app()
        with pytest.raises(AssertionError):
            delete_public_webform_build(app.domain, app.build_id)
        assert Application.get_db().doc_exist(app.build_id)
        assert get_blob_db().metadb.get_for_parent(app.build_id)
