import hashlib
import json
import os
from unittest import mock
from unittest.mock import patch

from couchdbkit.exceptions import ResourceConflict
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    Module,
    RemoteApp,
)
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.views.single_form_api import (
    FORM_API_APP_NOT_FOUND,
    FORM_API_CONFLICT,
    FORM_API_FIELD_NOT_PATCHABLE,
    FORM_API_FORM_NOT_FOUND,
    FORM_API_INVALID_FIELD_VALUE,
    FORM_API_MODULE_NOT_FOUND,
    FORM_API_PRECONDITION_FAILED,
    FORM_API_PRECONDITION_REQUIRED,
    ApiError,
    FormResource,
    _form_resource_dict,
    get_form_for_api,
    merge_patch,
    patch_form_for_api,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import (
    flag_disabled,
    flag_enabled,
    has_permissions,
    privilege_enabled,
)

ENTITY_XML = (
    '<?xml version="1.0"?>\n'
    '<!DOCTYPE root [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>\n'
    '<h:html xmlns:h="http://www.w3.org/1999/xhtml"><h:head>'
    '<h:title>&xxe;</h:title></h:head><h:body/></h:html>'
)


@flag_enabled('SINGLE_FORM_API')
class SingleFormApiViewTests(TestCase):
    username = 'single-form-api-user'
    password = 'correct-horse-battery-staple'
    non_admin_username = 'single-form-api-non-admin'
    non_admin_password = 'another-horse-battery-staple'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('single-form-view-domain')
        cls.user = WebUser.create(
            cls.domain.name,
            cls.username,
            cls.password,
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.user.is_superuser = True
        cls.user.save()

        cls.non_admin_user = WebUser.create(
            cls.domain.name,
            cls.non_admin_username,
            cls.non_admin_password,
            created_by=None,
            created_via=None,
            is_active=True,
        )

        cls.throttle_patcher = patch(
            'corehq.apps.api.resources.meta.HQThrottle.should_be_throttled', return_value=False
        )
        cls.throttle_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.throttle_patcher.stop()
        cls.non_admin_user.delete(cls.domain.name, deleted_by=None)
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.app = Application.new_app(self.domain.name, 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.module_id = module.unique_id
        self.form_id = form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

        self.client = Client()
        self.client.login(username=self.username, password=self.password)

    def _url(self, app_id=None, module_id=None, form_id=None):
        return reverse('single_form_api', kwargs={
            'domain': self.domain.name,
            'app_id': app_id or self.app._id,
            'module_id': module_id or self.module_id,
            'form_id': form_id or self.form_id,
        })

    def _etag(self):
        return self.client.get(self._url())['ETag']

    def test_endpoint_is_absent_without_the_feature_flag(self):
        with flag_disabled('SINGLE_FORM_API'):
            assert self.client.get(self._url()).status_code == 404
            assert self.client.head(self._url()).status_code == 404
            assert self.client.patch(
                self._url(), data=json.dumps({}), content_type='application/json',
            ).status_code == 404

    def test_head_matches_get_etag(self):
        assert self.client.head(self._url())['ETag'] == self.client.get(self._url())['ETag']

    def test_head_returns_404_for_missing_app(self):
        response = self.client.head(self._url(app_id='missing-app'))
        assert response.status_code == 404

    # The test client discards HEAD content the way a web server would, so
    # asserting on the content proves nothing. Content-Length still reports
    # the body the view built, which is the thing that must stay empty --
    # neither Django nor gunicorn strips it in production.
    def test_head_builds_no_body(self):
        assert self.client.head(self._url())['Content-Length'] == '0'

    def test_head_builds_no_body_for_an_error(self):
        assert self.client.head(self._url(form_id='missing-form'))['Content-Length'] == '0'

    def test_get_returns_bare_resource(self):
        response = self.client.get(self._url())
        assert response.status_code == 200
        body = response.json()
        assert body['unique_id'] == self.form_id
        assert 'source' in body
        assert 'errors' not in body
        assert response['ETag']

    def test_etag_is_the_hash_of_the_bytes_that_were_sent(self):
        # The contract a client relies on to recompute the ETag itself,
        # rather than treating it as an opaque token.
        response = self.client.get(self._url())
        digest = hashlib.sha256(response.content).hexdigest()
        assert response['ETag'] == f'"{digest}"'

    def test_response_body_is_canonical_json(self):
        body = self.client.get(self._url()).content
        assert body == json.dumps(
            json.loads(body), sort_keys=True, separators=(',', ':'), ensure_ascii=False
        ).encode('utf-8')

    def test_get_returns_404_for_missing_app(self):
        response = self.client.get(self._url(app_id='missing-app'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'app_not_found'

    def test_get_returns_404_for_missing_module(self):
        response = self.client.get(self._url(module_id='missing-module'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'module_not_found'

    def test_get_returns_404_for_missing_form(self):
        response = self.client.get(self._url(form_id='missing-form'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'form_not_found'

    def test_get_rejects_unauthenticated_request(self):
        assert Client().get(self._url()).status_code != 200

    @has_permissions(view_apps=False, edit_apps=False)
    def test_get_rejects_user_without_view_apps_permission(self):
        client = Client()
        client.login(username=self.non_admin_username, password=self.non_admin_password)
        assert client.get(self._url()).status_code != 200

    def test_patch_updates_only_specified_field(self):
        etag = self._etag()
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=etag,
        )
        assert response.status_code == 200
        assert response.json()['name']['en'] == 'Updated'

        app = Application.get(self.app._id)
        module = app.get_module_by_unique_id(self.module_id)
        assert module.get_form_by_unique_id(self.form_id).name['en'] == 'Updated'

    def test_patch_applies_source(self):
        etag = self._etag()
        new_xml = get_simple_form(xmlns='updated-xmlns')
        response = self.client.patch(
            self._url(), data=json.dumps({'source': new_xml}),
            content_type='application/json', HTTP_IF_MATCH=etag,
        )
        assert response.status_code == 200
        app = Application.get(self.app._id)
        module = app.get_module_by_unique_id(self.module_id)
        assert module.get_form_by_unique_id(self.form_id).source == new_xml

    def test_patch_accepts_the_whole_resource_it_returned(self):
        get = self.client.get(self._url())
        response = self.client.patch(
            self._url(), data=get.content,
            content_type='application/json', HTTP_IF_MATCH=get['ETag'],
        )
        assert response.status_code == 200, response.content

    def test_patch_merges_into_a_dict_instead_of_replacing_it(self):
        self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'English', 'fr': 'French'}}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        assert self.client.get(self._url()).json()['name'] == {
            'en': 'Updated', 'fr': 'French',
        }

    def test_patch_null_deletes_a_key(self):
        self.client.patch(
            self._url(), data=json.dumps({'comment': 'a comment'}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        self.client.patch(
            self._url(), data=json.dumps({'comment': None}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        assert not self.client.get(self._url()).json()['comment']

    def _patch_source(self, xml):
        return self.client.patch(
            self._url(), data=json.dumps({'source': xml}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )

    def test_patch_rejects_a_source_that_is_not_xml(self):
        response = self._patch_source('not xml at all')
        assert response.status_code == 400
        assert response.json()['errors'][0]['error'] == 'invalid_field_value'

    def test_patch_rejects_an_empty_source(self):
        assert self._patch_source('').status_code == 400

    def test_patch_rejects_a_source_declaring_entities(self):
        # Entities are refused by the parser; the point here is that the
        # refusal reaches the client as a 4xx rather than a crash.
        response = self._patch_source(ENTITY_XML)
        assert response.status_code == 400

    def test_a_rejected_source_leaves_the_form_alone(self):
        before = self.client.get(self._url()).json()
        self._patch_source('not xml at all')
        after = self.client.get(self._url()).json()
        assert after['xmlns'] == before['xmlns']
        assert after['source'] == before['source']

    def test_patch_rejects_an_explicit_null_source(self):
        # RFC 7396 says null deletes; a form cannot exist without XML, so
        # this has to be refused rather than silently ignored.
        response = self.client.patch(
            self._url(), data=json.dumps({'source': None}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        assert response.status_code == 400

    def test_if_match_accepts_a_list_of_tags(self):
        etag = self._etag()
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=f'"nomatch", {etag}',
        )
        assert response.status_code == 200

    def test_if_match_rejects_a_weak_validator(self):
        # RFC 9110 requires strong comparison for If-Match, so a weak tag
        # never matches, even one derived from the current ETag.
        etag = self._etag()
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=f'W/{etag}',
        )
        assert response.status_code == 412

    def test_no_field_can_be_deleted_into_a_crash(self):
        # RFC 7396 makes every field deletable, which is the corner these
        # keep failing in, so sweep the whole resource rather than guessing.
        for field in sorted(self.client.get(self._url()).json()):
            with self.subTest(field=field):
                response = self.client.patch(
                    self._url(), data=json.dumps({field: None}),
                    content_type='application/json', HTTP_IF_MATCH=self._etag(),
                )
                assert response.status_code < 500, response.content

    def test_patch_returns_the_updated_representation(self):
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        assert response.json()['name']['en'] == 'Updated'

    def test_the_patch_response_etag_hashes_the_patch_response(self):
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        digest = hashlib.sha256(response.content).hexdigest()
        assert response['ETag'] == f'"{digest}"'

    def test_patch_rejects_a_field_outside_the_allowlist(self):
        response = self.client.patch(
            self._url(), data=json.dumps({'auto_gps_capture': True}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        assert response.status_code == 400, response.content
        assert response.json()['errors'][0]['error'] == 'field_not_patchable'

    def test_patch_ignores_an_unchanged_field_outside_the_allowlist(self):
        # A client handing back a GET response must not be punished for the
        # fields it did not touch.
        get = self.client.get(self._url())
        response = self.client.patch(
            self._url(), data=get.content,
            content_type='application/json', HTTP_IF_MATCH=get['ETag'],
        )
        assert response.status_code == 200, response.content

    def test_if_match_star_is_accepted(self):
        # RFC 9110: "*" matches any current representation.
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Updated'}}),
            content_type='application/json', HTTP_IF_MATCH='*',
        )
        assert response.status_code == 200

    def test_head_reports_the_content_type_get_would_send(self):
        assert self.client.head(self._url())['Content-Type'] == 'application/json'

    def test_missing_form_says_the_form_is_missing(self):
        response = self.client.get(self._url(form_id='missing-form'))
        assert 'missing-form' in response.json()['errors'][0]['message']

    def test_throttling_does_not_run_before_authentication(self):
        with patch('corehq.apps.api.resources.meta.HQThrottle.should_be_throttled') as throttle:
            Client().get(self._url())
        assert not throttle.called

    def test_patch_etag_is_accepted_by_the_next_patch(self):
        first = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'First'}}),
            content_type='application/json', HTTP_IF_MATCH=self._etag(),
        )
        # no GET in between: the previous response carried the new ETag
        second = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Second'}}),
            content_type='application/json', HTTP_IF_MATCH=first['ETag'],
        )
        assert second.status_code == 200

    def test_patch_requires_if_match(self):
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'x'}}), content_type='application/json'
        )
        assert response.status_code == 428
        assert response.json()['errors'][0]['error'] == 'precondition_required'

    def test_patch_rejects_stale_if_match(self):
        response = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'x'}}),
            content_type='application/json', HTTP_IF_MATCH='"stale"',
        )
        assert response.status_code == 412
        assert response.json()['errors'][0]['error'] == 'precondition_failed'

    def test_patch_returns_invalid_json_for_bad_body(self):
        response = self.client.patch(
            self._url(), data='not json', content_type='application/json', HTTP_IF_MATCH=self._etag()
        )
        assert response.status_code == 400
        assert response.json()['errors'][0]['error'] == 'invalid_json'

    def test_patch_returns_404_for_missing_app(self):
        response = self.client.patch(
            self._url(app_id='missing-app'), data=json.dumps({}),
            content_type='application/json', HTTP_IF_MATCH='"anything"',
        )
        assert response.status_code == 404

    def test_patch_returns_404_for_saved_build(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)
        response = self.client.patch(
            self._url(app_id=build._id), data=json.dumps({'name': {'en': 'x'}}),
            content_type='application/json', HTTP_IF_MATCH='"anything"',
        )
        assert response.status_code == 404

    def test_patch_returns_conflict_on_concurrent_write(self):
        etag = self._etag()
        with patch.object(Application, 'save', side_effect=ResourceConflict):
            response = self.client.patch(
                self._url(), data=json.dumps({'name': {'en': 'x'}}),
                content_type='application/json', HTTP_IF_MATCH=etag,
            )
        assert response.status_code == 409
        assert response.json()['errors'][0]['error'] == 'conflict'

    def test_patch_rejects_unauthenticated_request(self):
        response = Client().patch(
            self._url(), data=json.dumps({}), content_type='application/json', HTTP_IF_MATCH='"x"'
        )
        assert response.status_code != 200

    @has_permissions(edit_apps=False)
    def test_patch_rejects_user_without_edit_apps_permission(self):
        client = Client()
        client.login(username=self.non_admin_username, password=self.non_admin_password)
        response = client.patch(
            self._url(), data=json.dumps({'name': {'en': 'x'}}),
            content_type='application/json', HTTP_IF_MATCH='"x"',
        )
        assert response.status_code != 200

    def test_rejects_put_method(self):
        response = self.client.put(self._url(), data=json.dumps({}), content_type='application/json')
        assert response.status_code == 405

    # --- round-trip ---

    def test_get_then_patch_with_its_etag_then_reject_reuse(self):
        etag = self._etag()
        first = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'First'}}),
            content_type='application/json', HTTP_IF_MATCH=etag,
        )
        assert first.status_code == 200

        second = self.client.patch(
            self._url(), data=json.dumps({'name': {'en': 'Second'}}),
            content_type='application/json', HTTP_IF_MATCH=etag,  # stale now
        )
        assert second.status_code == 412


class UpdateFormForApiTests(TestCase):
    domain = 'form-api-patch-domain'
    username = 'form-api-patch-user'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'correct-horse-battery-staple',
            created_by=None, created_via=None, is_active=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.app = Application.new_app(self.domain, 'Test App')
        self.module = self.app.add_module(Module.new_module('Module One', lang='en'))
        self.form = self.module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.form.comment = 'original comment'
        self.module_id = self.module.unique_id
        self.form_id = self.form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

    def _etag(self):
        form, _ = get_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id
        )
        return FormResource(form).get_etag()

    def test_updates_only_specified_fields(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'Renamed'}}, self._etag(), self.user
        )

        assert result.success is True
        assert form.name['en'] == 'Renamed'
        assert form.comment == 'original comment'  # untouched

    def test_bumps_app_version(self):
        old_version = self.app.version
        patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'Renamed'}}, self._etag(), self.user
        )
        assert Application.get(self.app._id).version > old_version

    def test_applies_source_via_save_xform(self):
        new_xml = get_simple_form(xmlns='xmlns-2')
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'source': new_xml}, self._etag(), self.user
        )
        assert result.success is True
        assert form.source == new_xml

    def test_leaves_xml_untouched_when_source_absent(self):
        original_source = self.form.source
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'Renamed'}}, self._etag(), self.user
        )
        assert form.source == original_source

    def test_a_spoofed_unique_id_is_refused(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'unique_id': 'spoofed-id', 'name': {'en': 'Renamed'}}, self._etag(), self.user
        )
        assert result.errors[0].error == FORM_API_FIELD_NOT_PATCHABLE

    def test_a_spoofed_xmlns_is_refused(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'xmlns': 'spoofed-xmlns', 'name': {'en': 'Renamed'}}, self._etag(), self.user
        )
        assert result.errors[0].error == FORM_API_FIELD_NOT_PATCHABLE

    def test_returns_invalid_field_value_for_wrong_type(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': 'not-a-dict'}, self._etag(), self.user
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_INVALID_FIELD_VALUE

    def test_returns_precondition_required_when_if_match_missing(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'x'}}, None, self.user
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_PRECONDITION_REQUIRED

    def test_returns_precondition_failed_for_stale_if_match(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'x'}}, '"stale-etag"', self.user
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_PRECONDITION_FAILED

    def test_propagates_a_failed_lookup(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, 'missing-module', self.form_id, {}, None, self.user
        )
        assert result.errors[0].error == FORM_API_MODULE_NOT_FOUND

    def test_does_not_save_on_any_failure(self):
        old_version = self.app.version
        patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'not_a_real_field': 'x'}, self._etag(), self.user
        )
        assert Application.get(self.app._id).version == old_version

    def test_returns_conflict_when_save_hits_concurrent_write(self):
        etag = self._etag()
        with patch.object(Application, 'save', side_effect=ResourceConflict):
            form, result = patch_form_for_api(
                self.domain, self.app._id, self.module_id, self.form_id,
                {'name': {'en': 'x'}}, etag, self.user,
            )

        assert result.success is False
        assert result.errors[0].error == FORM_API_CONFLICT

    def test_a_losing_write_leaves_the_xml_untouched(self):
        # save_xform only stages the XML, and app.save() writes the blob and
        # the doc inside one rollback scope, so losing the save race must
        # not leave the new XML behind without the fields that go with it.
        original_source = self.form.source
        etag = self._etag()

        def commit_a_conflicting_change(app, form, xml, **kw):
            other = Application.get(app._id)
            other.name = 'Renamed By Someone Else'
            other.save()
            return save_xform(app, form, xml, **kw)

        with patch(f'{patch_form_for_api.__module__}.save_xform',
                   side_effect=commit_a_conflicting_change):
            form, result = patch_form_for_api(
                self.domain, self.app._id, self.module_id, self.form_id,
                {'source': get_simple_form(xmlns='xmlns-clobber')}, etag, self.user,
            )

        assert result.errors[0].error == FORM_API_CONFLICT
        assert Application.get(self.app._id).get_form(self.form_id).source == original_source


class GetFormForApiTests(TestCase):
    def setUp(self):
        self.domain = create_domain('form-api-get-domain')
        self.addCleanup(self.domain.delete)
        self.app = Application.new_app(self.domain.name, 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.module_id = module.unique_id
        self.form_id = self.form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

    def test_returns_form_on_success(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, self.module_id, self.form_id)

        assert result.success is True
        assert result.errors == []
        assert form.unique_id == self.form_id

    def test_treats_missing_app_as_not_found(self):
        form, result = get_form_for_api(self.domain.name, 'missing-app', self.module_id, self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_treats_saved_build_as_not_found(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)

        form, result = get_form_for_api(self.domain.name, build._id, self.module_id, self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_treats_a_deleted_app_as_not_found(self):
        self.app.delete_app()
        self.app.save()

        form, result = get_form_for_api(
            self.domain.name, self.app._id, self.module_id, self.form_id
        )

        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_treats_a_remote_app_as_not_found(self):
        remote = RemoteApp.new_app(self.domain.name, 'Remote App')
        remote.save()
        self.addCleanup(remote.delete)

        form, result = get_form_for_api(
            self.domain.name, remote._id, self.module_id, self.form_id
        )

        assert result.errors == [ApiError(FORM_API_APP_NOT_FOUND, mock.ANY)]

    def test_returns_module_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, 'missing-module', self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_MODULE_NOT_FOUND, mock.ANY)]

    def test_returns_form_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, self.module_id, 'missing-form')

        assert result.success is False
        assert result.errors[0].error == FORM_API_FORM_NOT_FOUND


class MergePatchTests(SimpleTestCase):
    """RFC 7396 semantics, which the API adopts wholesale."""

    def test_merges_nested_objects_rather_than_replacing_them(self):
        merged = merge_patch({'a': {'x': 1, 'y': 2}}, {'a': {'y': 3}})
        assert merged == {'a': {'x': 1, 'y': 3}}

    def test_null_deletes_a_key(self):
        assert merge_patch({'a': 1, 'b': 2}, {'a': None}) == {'b': 2}

    def test_null_for_an_absent_key_is_a_noop(self):
        assert merge_patch({'b': 2}, {'a': None}) == {'b': 2}

    def test_lists_replace_wholesale(self):
        assert merge_patch({'a': [1, 2, 3]}, {'a': [9]}) == {'a': [9]}

    def test_a_scalar_replaces_an_object(self):
        assert merge_patch({'a': {'x': 1}}, {'a': 'flat'}) == {'a': 'flat'}

    def test_leaves_untouched_keys_alone(self):
        assert merge_patch({'a': 1, 'b': 2}, {'a': 9}) == {'a': 9, 'b': 2}


class FormResourceEtagTests(TestCase):
    def setUp(self):
        self.app = Application.new_app('form-etag-domain', 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.app.save()
        self.addCleanup(self.app.delete)

    def test_stable_across_reloading_unchanged_form(self):
        reloaded = Application.get(self.app._id).get_form(self.form.unique_id)
        assert FormResource(self.form).get_etag() == FormResource(reloaded).get_etag()

    def test_changes_when_form_content_changes(self):
        before = FormResource(self.form).get_etag()
        self.form.name = {'en': 'Renamed'}
        after = FormResource(self.form).get_etag()
        assert before != after

    def test_is_a_quoted_string(self):
        etag = FormResource(self.form).get_etag()
        assert etag.startswith('"') and etag.endswith('"')


class FormResourceDictTests(TestCase):
    def setUp(self):
        app = Application.new_app('form-resource-dict-domain', 'Test App')
        module = app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))

    def test_includes_source_key(self):
        resource = _form_resource_dict(self.form)
        assert resource['source'] == self.form.source

    def test_does_not_include_validation_cache(self):
        # Assigning validation_cache also writes a dynamic property onto
        # the document, so every in-memory form carries the key while one
        # reloaded from Couch has it stripped by FormBase.wrap. Leaving it
        # in the resource would give one unchanged form two ETags.
        self.form.set_validation_cache('some cached value')
        resource = _form_resource_dict(self.form)
        assert 'validation_cache' not in resource

    def test_includes_form_json_fields(self):
        resource = _form_resource_dict(self.form)
        assert resource['unique_id'] == self.form.unique_id
        assert resource['name'] == self.form.name


# ``case_in_form`` locks /data/question2; changing its bind changes the
# question's signature, which is what the locked-question check compares.
LOCKED_BIND = '<bind nodeset="/data/question2" type="xsd:string" vellum:lock="all" />'
EDITED_LOCKED_BIND = (
    '<bind nodeset="/data/question2" type="xsd:string" constraint="0" vellum:lock="all" />'
)


@flag_enabled('SINGLE_FORM_API')
class LockedQuestionApiTests(TestCase):
    """A locked question must be no more editable through this API than it is
    in the form builder, which rejects the edit unless the user holds
    ``edit_locked_questions_in_apps``.
    """

    username = 'locked-question-user'
    password = 'correct-horse-battery-staple'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('locked-question-domain')
        cls.user = WebUser.create(
            cls.domain.name, cls.username, cls.password,
            created_by=None, created_via=None, is_active=True,
        )
        cls.throttle_patcher = patch(
            'corehq.apps.api.resources.meta.HQThrottle.should_be_throttled', return_value=False
        )
        cls.throttle_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.throttle_patcher.stop()
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        path = os.path.join(os.path.dirname(__file__), 'data', 'case_in_form.xml')
        with open(path, encoding='utf-8') as f:
            source = f.read()
        self.app = Application.new_app(self.domain.name, 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        module.case_type = 'test'
        form = module.new_form('Form One', lang='en', attachment=source)
        self.module_id = module.unique_id
        self.form_id = form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

        self.client = Client()
        self.client.login(username=self.username, password=self.password)

    def _url(self):
        return reverse('single_form_api', kwargs={
            'domain': self.domain.name,
            'app_id': self.app._id,
            'module_id': self.module_id,
            'form_id': self.form_id,
        })

    def _edit_the_locked_question(self):
        get = self.client.get(self._url())
        edited = get.json()['source'].replace(LOCKED_BIND, EDITED_LOCKED_BIND)
        assert edited != get.json()['source'], 'fixture no longer locks question2'
        return self.client.patch(
            self._url(), data=json.dumps({'source': edited}),
            content_type='application/json', HTTP_IF_MATCH=get['ETag'],
        )

    def test_patch_cannot_edit_a_locked_question_without_the_permission(self):
        with privilege_enabled(privileges.LOCKED_ADMIN_QUESTIONS), \
                has_permissions(view_apps=True, edit_apps=True):
            assert self._edit_the_locked_question().status_code == 403

    def test_patch_can_edit_a_locked_question_with_the_permission(self):
        with privilege_enabled(privileges.LOCKED_ADMIN_QUESTIONS), \
                has_permissions(view_apps=True, edit_apps=True,
                                edit_locked_questions_in_apps=True):
            assert self._edit_the_locked_question().status_code == 200


@flag_enabled('SINGLE_FORM_API')
class ShadowFormApiTests(TestCase):
    """A shadow form derives its XML and actions from the form it shadows,
    so neither is settable; patching them must fail cleanly rather than
    crash on the missing setter."""

    domain = 'shadow-form-domain'
    username = 'shadow-form-user'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(
            cls.domain, cls.username, 'correct-horse-battery-staple',
            created_by=None, created_via=None, is_active=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.app = Application.new_app(self.domain, 'Test App')
        module = self.app.add_module(AdvancedModule.new_module('Module One', lang='en'))
        module.new_form('Real Form', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        shadow = module.new_shadow_form('Shadow Form', lang='en')
        self.module_id = module.unique_id
        self.form_id = shadow.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

    def _patch(self, body):
        form, _ = get_form_for_api(self.domain, self.app._id, self.module_id, self.form_id)
        etag = FormResource(form).get_etag()
        return patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id, body, etag, self.user,
        )

    def test_etag_is_stable_between_identical_reads(self):
        # Without this a shadow form is unwritable: its regenerated source
        # changes the hash, so If-Match can never match.
        first, _ = get_form_for_api(self.domain, self.app._id, self.module_id, self.form_id)
        second, _ = get_form_for_api(self.domain, self.app._id, self.module_id, self.form_id)
        assert FormResource(first).get_etag() == FormResource(second).get_etag()

    def test_rejects_a_source_patch(self):
        form, result = self._patch({'source': get_simple_form(xmlns='xmlns-2')})
        assert result.errors[0].error == FORM_API_INVALID_FIELD_VALUE

    def test_allows_an_ordinary_field(self):
        form, result = self._patch({'comment': 'a comment'})
        assert result.success is True, result.errors
