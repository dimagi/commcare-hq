# from django.db import models
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
import requests


class JsonApiError(Exception):
    pass


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, host, username, password):
        self.baseurl = host + '/api/'
        self.header = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError if HTTP status is not in the 200 (OK) range
        """
        if not 200 <= response.status_code < 300:
            raise JsonApiError('API request failed with HTTP status %s: %s' %
                               (response.status_code, response.text))
        return response.status_code, response.json()

    def get(self, path, **kwargs):
        try:
            response = requests.get(self.baseurl + path, header=self.header, auth=self.auth, **kwargs)
        except Exception as err:  # TODO: What exception?! (socket error; authentication error; ...?)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def post(self, path, data, **kwargs):
        try:
            response = requests.post(self.baseurl + path, data, header=self.header, auth=self.auth, **kwargs)
        except Exception as err:  # TODO: What exception?! (socket error; authentication error; ...?)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)


class FixtureManager(object):
    """
    Reuses the Django manager pattern for fixtures
    """

    def __init__(self, model_class, domain, tag):
        self.model_class = model_class
        self.domain = domain
        self.tag = tag

    def get(self, id_):
        data_type = FixtureDataType.by_domain_tag(self.domain, self.tag).one()
        item = FixtureDataItem.by_field_value(self.domain, data_type, 'id_', id_).one()
        return self.model_class(_fixture_id=item.get_id, **item.fields)

    def all(self):
        for item in FixtureDataItem.get_item_list(self.domain, self.tag):
            yield self.model_class(_fixture_id=item.get_id, **item.fields)


class Dhis2OrgUnit(object):
    """
    Simplify the management of DHIS2 Organisation Units, which are
    stored in a lookup table.
    """

    objects = None  # Manager is set outside of class definition so that we can pass the class to the manager

    def __init__(self, id_, name, _fixture_id=None):
        self.id_ = id_  # param is called "id_" because "id" is a built-in
        self.name = name
        self._fixture_id = _fixture_id

    def save(self):
        data_type = FixtureDataType.by_domain_tag(self.objects.domain, self.objects.tag).one()
        data_item = FixtureDataItem()
        data_item.data_type_id = data_type.get_id
        data_item.domain = self.objects.domain
        data_item.fields = {
            'id_': self.id_,   # Use key "id_" instead of "id" so we have the option of passing as kwargs to __init__
            'name': self.name  # ... which is exactly what FixtureManager does in objects.get() and objects.all()
        }
        data_item.save()
        self._fixture_id = data_item.get_id

    def delete(self):
        if self._fixture_id is None:
            return
        item = FixtureDataItem.get(self._fixture_id)
        item.delete()

Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, 'dhis2', 'dhis2_org_unit')
