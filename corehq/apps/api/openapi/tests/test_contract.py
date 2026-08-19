"""Validate real API responses against the OpenAPI spec generated for them.

``test_examples_validate.py`` checks that a checked-in example matches the
schema it's attached to -- but an example and its schema can be
self-consistently wrong: both silently agree with each other while
disagreeing with what the API actually returns. This module instead drives
the real request path (via ``APIResourceTest``) and checks the *real*
response against the spec, in both directions:

* every field the real response returns must be described, with the right
  shape, by the spec (``jsonschema`` validation catches type, ``required``,
  ``enum`` and nullability mistakes that a plain "is this a subset of the
  property names" check would miss);
* every property the spec declares -- other than ones marked ``writeOnly``,
  which only ever appear in a request body -- must actually show up in the
  real response. Without this direction, a schema could describe fields the
  API never returns, or a whole-bundle ``dehydrate()`` could inject fields
  the schema never mentions, and neither would be caught by the forward
  check above.
"""

import json

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.openapi.tests.oas_validation import (
    assert_matches_schema,
    declared_response_fields,
)
from corehq.apps.api.resources import v0_5
from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


def _find_path(document, *, detail):
    """The one path in ``document`` that is (or isn't) a detail path.

    Rather than hard-coding the detail URL's path-parameter name (which
    is an implementation detail of each resource's ``Meta`` and not worth
    duplicating here), find it by shape: a detail path is the one whose
    last URL segment is a ``{param}``. A resource's ``prepend_urls``
    endpoints (e.g. ``{pk}/activate/``) also route under the detail path
    but are longer than either the plain list or plain detail path, so
    the shortest match among same-shaped candidates is the real one.
    """
    matches = [
        path
        for path in document['paths']
        if path.rstrip('/').endswith('}') == detail
    ]
    assert matches, f'expected a {"detail" if detail else "list"} path'
    return min(matches, key=len)


def _list_item_schema(document):
    path = _find_path(document, detail=False)
    response_schema = document['paths'][path]['get']['responses']['200'][
        'content'
    ]['application/json']['schema']
    return (
        path,
        response_schema,
        response_schema['properties']['objects']['items'],
    )


def _detail_schema(document):
    path = _find_path(document, detail=True)
    schema = document['paths'][path]['get']['responses']['200']['content'][
        'application/json'
    ]['schema']
    return path, schema


def _assert_response_and_spec_agree(
    document, item_schema, instance, *, optional=()
):
    """Both directions of the contract, for one object-shaped response.

    ``optional`` names spec properties this particular instance is allowed
    to omit (e.g. a field that is only present under conditions this test
    doesn't exercise), each of which the caller should justify at the call
    site.
    """
    assert_matches_schema(
        document, item_schema, instance, context='real response'
    )
    should_appear = declared_response_fields(item_schema['properties']) - set(
        optional
    )
    missing = should_appear - set(instance)
    assert not missing, (
        f'spec properties never appear in the real response: {sorted(missing)}'
    )


class ApiSpecContract:
    """Both directions of the contract, for any documented resource.

    The assertions do not vary by resource: fetch the list and the detail
    endpoint, validate each real response against the published schema,
    and check every non-``writeOnly`` property actually appears. Only the
    fixture varies. Written out per resource -- as it was for user-v1 and
    group-v1 -- a correction to one copy leaves the others behind, and
    adding a third resource means transcribing the assertions again.

    A subclass supplies ``resource``/``api_name`` (read by
    ``APIResourceTest``), the ``doc_slug`` its spec is published under, a
    ``record_id`` for the detail endpoint, and a ``setUpClass`` that
    creates and indexes that record.

    Deliberately not named ``Test*``: pytest would collect it on its own,
    where it has no resource and no record.
    """

    doc_slug = None

    @property
    def record_id(self):
        """The id of the record ``setUpClass`` created and indexed."""
        raise NotImplementedError

    def test_list_response_conforms_to_the_spec(self):
        document = build_all()[self.doc_slug]
        _, list_schema, item_schema = _list_item_schema(document)

        response = self._assert_auth_get_resource(self.list_endpoint)
        assert response.status_code == 200, response.content
        payload = json.loads(response.content)

        assert_matches_schema(
            document,
            list_schema,
            payload,
            context=f'{self.doc_slug} list response',
        )
        [record] = payload['objects']
        _assert_response_and_spec_agree(document, item_schema, record)

    def test_detail_response_conforms_to_the_spec(self):
        document = build_all()[self.doc_slug]
        _, detail_schema = _detail_schema(document)

        response = self._assert_auth_get_resource(
            self.single_endpoint(self.record_id)
        )
        assert response.status_code == 200, response.content
        payload = json.loads(response.content)

        _assert_response_and_spec_agree(document, detail_schema, payload)


@es_test(requires=[user_adapter], setup_class=True)
class TestUserApiMatchesItsSpec(ApiSpecContract, APIResourceTest):
    resource = v0_5.CommCareUserResource
    api_name = 'v1'
    doc_slug = 'user-v1'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.commcare_user = CommCareUser.create(
            domain=cls.domain.name,
            username='listed@{}.commcarehq.org'.format(cls.domain.name),
            password='**********',
            created_by=None,
            created_via=None,
            first_name='Listed',
            last_name='User',
        )
        cls.addClassCleanup(cls.commcare_user.delete, cls.domain.name, None)
        user_adapter.index(cls.commcare_user, refresh=True)
        cls.addClassCleanup(
            user_adapter.delete, cls.commcare_user._id, refresh=True
        )

    @property
    def record_id(self):
        return self.commcare_user._id


@es_test(requires=[group_adapter], setup_class=True)
class TestGroupApiMatchesItsSpec(ApiSpecContract, APIResourceTest):
    resource = v0_5.GroupResource
    api_name = 'v1'
    doc_slug = 'group-v1'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = Group(name='contract-test', domain=cls.domain.name)
        cls.group.save()
        cls.addClassCleanup(cls.group.delete)
        group_adapter.index(cls.group, refresh=True)
        cls.addClassCleanup(group_adapter.delete, cls.group._id, refresh=True)

    @property
    def record_id(self):
        return self.group._id
