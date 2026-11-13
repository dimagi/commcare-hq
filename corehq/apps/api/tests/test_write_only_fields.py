import pytest
from tastypie.bundle import Bundle

from corehq.apps.api.resources.v0_5 import CommCareUserResource


@pytest.mark.parametrize("name", CommCareUserResource.WRITE_ONLY_FIELDS)
def test_write_only_fields_are_declared(name):
    assert name in CommCareUserResource.base_fields


@pytest.mark.parametrize("name", CommCareUserResource.WRITE_ONLY_FIELDS)
def test_declared_without_an_attribute(name):
    # With an attribute, tastypie would read the value off the user object --
    # which for `password` would mean dehydrating the stored hash.
    assert CommCareUserResource.base_fields[name].attribute is None


def test_dehydrate_removes_every_write_only_field():
    resource = CommCareUserResource(api_name='v1')
    data = {name: 'supplied' for name in resource.WRITE_ONLY_FIELDS}
    data['username'] = 'fake_user'
    resource.dehydrate(Bundle(data=data))
    assert set(data) == {'username'}


def test_dehydrate_tolerates_absent_fields():
    # GET never supplies them, so removal must not require their presence
    resource = CommCareUserResource(api_name='v1')
    data = {'username': 'fake_user'}
    resource.dehydrate(Bundle(data=data))
    assert data == {'username': 'fake_user'}
