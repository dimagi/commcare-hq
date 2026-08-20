import hashlib
import json
from unittest import mock
from unittest.mock import patch

from couchdbkit.exceptions import ResourceConflict
from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.views.single_form_api import (
    FORM_API_APP_NOT_FOUND,
    FORM_API_CONFLICT,
    FORM_API_DOC_TYPE_MISMATCH,
    FORM_API_FORM_NOT_FOUND,
    FORM_API_INVALID_FIELD_VALUE,
    FORM_API_MODULE_NOT_FOUND,
    FORM_API_PRECONDITION_FAILED,
    FORM_API_PRECONDITION_REQUIRED,
    FORM_API_UNRECOGNIZED_FIELD,
    ApiError,
    FormResource,
    create_form_patch,
    _form_resource_dict,
    get_form_for_api,
    patch_form_for_api,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import has_permissions


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

class UpdateFormForApiTests(TestCase):
    domain = 'form-api-patch-domain'

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
            {'name': {'en': 'Renamed'}}, self._etag(),
        )

        assert result.success is True
        assert form.name['en'] == 'Renamed'
        assert form.comment == 'original comment'  # untouched

    def test_bumps_app_version(self):
        old_version = self.app.version
        patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'Renamed'}}, self._etag(),
        )
        assert Application.get(self.app._id).version > old_version

    def test_applies_source_via_save_xform(self):
        new_xml = get_simple_form(xmlns='xmlns-2')
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'source': new_xml}, self._etag(),
        )
        assert result.success is True
        assert form.source == new_xml

    def test_leaves_xml_untouched_when_source_absent(self):
        original_source = self.form.source
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'Renamed'}}, self._etag(),
        )
        assert form.source == original_source

    def test_unique_id_in_body_is_silently_ignored(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'unique_id': 'spoofed-id', 'name': {'en': 'Renamed'}}, self._etag(),
        )
        assert result.success is True
        assert form.unique_id == self.form_id  # NOT 'spoofed-id'

    def test_xmlns_in_body_is_silently_ignored(self):
        original_xmlns = self.form.xmlns
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'xmlns': 'spoofed-xmlns', 'name': {'en': 'Renamed'}}, self._etag(),
        )
        assert result.success is True
        assert form.xmlns == original_xmlns

    def test_returns_invalid_field_value_for_wrong_type(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': 'not-a-dict'}, self._etag(),
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_INVALID_FIELD_VALUE

    def test_returns_precondition_required_when_if_match_missing(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'x'}}, None,
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_PRECONDITION_REQUIRED

    def test_returns_precondition_failed_for_stale_if_match(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'name': {'en': 'x'}}, '"stale-etag"',
        )
        assert result.success is False
        assert result.errors[0].error == FORM_API_PRECONDITION_FAILED

    def test_propagates_a_failed_lookup(self):
        form, result = patch_form_for_api(
            self.domain, self.app._id, 'missing-module', self.form_id, {}, None
        )
        assert result.errors[0].error == FORM_API_MODULE_NOT_FOUND

    def test_does_not_save_on_any_failure(self):
        old_version = self.app.version
        patch_form_for_api(
            self.domain, self.app._id, self.module_id, self.form_id,
            {'not_a_real_field': 'x'}, self._etag(),
        )
        assert Application.get(self.app._id).version == old_version

    def test_returns_conflict_when_save_hits_concurrent_write(self):
        etag = self._etag()
        with patch.object(Application, 'save', side_effect=ResourceConflict):
            form, result = patch_form_for_api(
                self.domain, self.app._id, self.module_id, self.form_id,
                {'name': {'en': 'x'}}, etag,
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
                {'source': get_simple_form(xmlns='xmlns-clobber')}, etag,
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

    def test_returns_module_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, 'missing-module', self.form_id)

        assert result.success is False
        assert result.errors == [ApiError(FORM_API_MODULE_NOT_FOUND, mock.ANY)]

    def test_returns_form_not_found(self):
        form, result = get_form_for_api(self.domain.name, self.app._id, self.module_id, 'missing-form')

        assert result.success is False
        assert result.errors[0].error == FORM_API_FORM_NOT_FOUND


class CreateFormPatchTests(TestCase):
    def setUp(self):
        app = Application.new_app('create-form-patch-domain', 'Test App')
        module = app.add_module(Module.new_module('Module One', lang='en'))
        self.form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))

    def test_returns_only_specified_fields(self):
        fields_to_set, errors = create_form_patch(self.form, {'name': {'en': 'Renamed'}})

        assert errors == []
        assert fields_to_set == {'name': {'en': 'Renamed'}}

    def test_returns_unrecognized_field_error(self):
        fields_to_set, errors = create_form_patch(self.form, {'not_a_real_field': 'x'})

        assert fields_to_set is None
        assert errors == [ApiError(FORM_API_UNRECOGNIZED_FIELD, mock.ANY)]

    def test_returns_doc_type_mismatch_error(self):
        fields_to_set, errors = create_form_patch(self.form, {'doc_type': 'AdvancedForm'})

        assert fields_to_set is None
        assert errors == [ApiError(FORM_API_DOC_TYPE_MISMATCH, mock.ANY)]

    def test_doc_type_matching_is_a_noop(self):
        fields_to_set, errors = create_form_patch(self.form, {'doc_type': 'Form'})

        assert errors == []
        assert 'doc_type' not in fields_to_set

    def test_unique_id_and_xmlns_are_dropped_not_overwritten(self):
        fields_to_set, errors = create_form_patch(
            self.form, {'unique_id': 'spoofed-id', 'xmlns': 'spoofed-xmlns'}
        )

        assert errors == []
        assert 'unique_id' not in fields_to_set
        assert 'xmlns' not in fields_to_set

    def test_source_is_allowed_but_not_included_in_fields_to_set(self):
        fields_to_set, errors = create_form_patch(self.form, {'source': '<h:html/>'})

        assert errors == []
        assert 'source' not in fields_to_set


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
