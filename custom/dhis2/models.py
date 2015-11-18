from __future__ import print_function
from datetime import date
import json
import logging
from casexml.apps.case.models import CommCareCase
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FieldList, FixtureItemField
from couchdbkit import ResourceNotFound
from dimagi.ext.couchdbkit import *
from dimagi.utils.couch.cache import cache_core
import requests
from toggle.models import Toggle


logger = logging.getLogger(__name__)


class Dhis2Settings(Document):
    domain = StringProperty()
    dhis2 = DictProperty()

    @classmethod
    def for_domain(cls, domain):
        res = cache_core.cached_view(
            cls.get_db(),
            "by_domain_doc_type_date/view",
            key=[domain, 'Dhis2Settings', None],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap)
        return res[0] if len(res) > 0 else None

    @classmethod
    def all_enabled(cls):
        """
        Yields settings of all domains for which "enabled" is true
        """
        try:
            toggle = Toggle.get('dhis2_domain')
        except ResourceNotFound:
            return
        for domain in toggle.enabled_users:
            if domain.startswith('domain:'):
                # If the "domain" namespace is given, strip it off
                domain = domain.split(':')[1]
            settings = cls.for_domain(domain)
            if settings and settings.is_enabled():
                yield settings

    @classmethod
    def is_enabled_for_domain(cls, domain):
        settings = cls.for_domain(domain)
        return settings is not None and settings.is_enabled()

    def is_enabled(self):
        return self.dhis2['enabled']


class JsonApiError(Exception):
    """
    JsonApiError is raised for HTTP or socket errors.
    """
    pass


class Dhis2ApiQueryError(JsonApiError):
    """
    Dhis2ApiQueryError is raised when the API returns an unexpected response.
    """
    pass


class Dhis2ConfigurationError(Exception):
    """
    DHIS2 API Integration has not been configured correctly.
    """
    pass


class Dhis2IntegrationError(Exception):
    """
    A failure has occurred in CommCareHQ related to but not caused by DHIS2.
    """
    pass


def json_serializer(obj):
    """
    A JSON serializer that serializes dates and times
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, host, username, password):
        self.baseurl = host + '/api/'
        self.headers = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError: if HTTP status is not in the 200 (OK) range
        """
        if 200 <= response.status_code < 300:
            return response.json()
        else:
            raise JsonApiError('API request to %s failed with HTTP status %s: %s' %
                               (response.url, response.status_code, response.text))

    def get(self, path, **kwargs):
        logger.debug('DHIS2: GET %s: \n'
                     '    Headers: %s\n'
                     '    kwargs: %s',
                     self.baseurl + path, self.headers, kwargs)
        try:
            response = requests.get(self.baseurl + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logger.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'get', 'url': self.baseurl + path, 'headers': self.headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def post(self, path, data, **kwargs):
        # Make a copy of self.headers because setting content type on requests that don't send content is bad
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logger.debug('DHIS2: POST %s: \n'
                     '    Headers: %s\n'
                     '    Data: %s\n'
                     '    kwargs: %s',
                     self.baseurl + path, self.headers, json_data, kwargs)
        try:
            response = requests.post(self.baseurl + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logger.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'post', 'url': self.baseurl + path, 'data': json_data, 'headers': headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def put(self, path, data, **kwargs):
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logger.debug('DHIS2: PUT %s: \n'
                     '    Headers: %s\n'
                     '    Data: %s\n'
                     '    kwargs: %s',
                     self.baseurl + path, self.headers, json_data, kwargs)
        try:
            response = requests.put(self.baseurl + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logger.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'put', 'url': self.baseurl + path, 'data': json_data, 'headers': headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)


class Dhis2Api(object):

    def __init__(self, host, username, password, top_org_unit_name=None):
        self._username = username  # Used when creating DHIS2 events from CCHQ form data
        self.top_org_unit_name = top_org_unit_name
        self._top_org_unit = None
        self._request = JsonApiRequest(host, username, password)
        self._tracked_entity_attributes = {}  # Cache known tracked entity attribute names and IDs
        self._not_tracked_entity_attributes = (
            # These fields are returned by DHIS2, but cannot be sent in a POST
            # or PUT request as tracked entity attributes. DHIS2 will 500.
            'Instance',
            'Created',
            'Last updated',
            'Org unit',
            'Tracked entity',
        )
        self._data_elements = {}  # Like _tracked_entity_attributes, but for events data

    def _fetch_tracked_entity_attributes(self):
        response = self._request.get('trackedEntityAttributes', params={'links': 'false', 'paging': 'false'})
        for te in response['trackedEntityAttributes']:
            self._tracked_entity_attributes[te['name']] = te['id']

    def _fetch_data_elements(self):
        response = self._request.get('dataElements', params={'links': 'false', 'paging': 'false'})
        for de in response['dataElements']:
            self._data_elements[de['name']] = de['id']

    def _data_to_attributes(self, data):
        """
        Convert tracked entity instance data, as returned by DHIS2, into a
        list of attributes, as accepted by DHIS2.
        """
        for attr in self._not_tracked_entity_attributes:
            data.pop(attr, None)
        # Convert data keys to tracked entity attribute IDs
        if any(key not in self._tracked_entity_attributes for key in data):
            # We are going to have to fetch at least one tracked entity
            # attribute ID. Fetch them all to avoid multiple API requests.
            self._fetch_tracked_entity_attributes()
        # Create a list of attributes, looking up the attribute ID of each one
        attributes = [{
            'attribute': self.get_te_attr_id(key),
            'value': value
        } for key, value in data.iteritems()]
        return attributes

    def add_te_inst(self, te_name, ou_id, instance_data):
        """
        Add a tracked entity instance

        :param te_name: Name of the tracked entity. Add or override its ID in data.
        :param ou_id: Add or override organisation unit ID in data.
        :param instance_data: A dictionary of entity attributes and values
        :return: New tracked entity instance ID

        .. Note:: If te_name is not specified, then `data` must include the
                  *ID* of the tracked entity, not its name.

        Example request: ::

            {
                "orgUnit": "Thu5YoRCV8y",
                "trackedEntity": "djYzXj7pXIl",
                "attributes": [{
                    "attribute": "HHsieCWv2XR",
                    "value": "05e17037-4d36-4cb3-af7d-5d9db6ff6b7f"
                }]
            }

        Example response: ::

            {
                "status": "SUCCESS",
                "importCount": {
                    "imported": 1,
                    "updated": 0,
                    "ignored": 0,
                    "deleted": 0
                },
                "reference": "HI2SHTzkrHo"
            }


        """
        request_data = {
            'trackedEntity': self.get_te_id(te_name),
            'orgUnit': ou_id,
            'attributes': self._data_to_attributes(instance_data)
        }
        response = self._request.post('trackedEntityInstances', request_data)
        if response['status'] != 'SUCCESS':
            raise Dhis2ApiQueryError('Failed to create instance of tracked entity "%s". DHIS2 API error: %s' %
                                     (te_name, response))
        return response['reference']

    def update_te_inst(self, instance_data):
        """
        Update a tracked entity instance with the given data

        :param instance_data: Tracked entity instance data. Must include its ID,
                     organisation unit and tracked entity type
        """
        try:
            te_inst_id = instance_data.pop('Instance')
            ou_id = instance_data.pop('Org unit')
        except KeyError as err:
            raise KeyError('Mandatory attribute missing from tracked entity instance data: %s' % err)
        request_data = {
            'trackedEntityInstance': te_inst_id,
            'orgUnit': ou_id,
            'attributes': self._data_to_attributes(instance_data)
        }
        response = self._request.put('trackedEntityInstances/' + te_inst_id, request_data)
        if response['status'] != 'SUCCESS':
            logger.error('Failed to update instance of tracked entity "%s". DHIS2 API error: %s',
                         te_inst_id, response)

    def get_top_org_unit(self):
        """
        Return the top-most organisation unit.
        """
        if self._top_org_unit is None:
            if self.top_org_unit_name:
                # A top organisation unit has been specified in the settings. Use that
                response = self._request.get('organisationUnits',
                                             params={'links': 'false',
                                                     'query': self.top_org_unit_name})
                self._top_org_unit = response['organisationUnits'][0]
            else:
                # Traverse up the tree of organisation units
                org_units_json = self._request.get('organisationUnits', params={'links': 'false'})
                org_unit = org_units_json['organisationUnits'][0]
                # The List response doesn't include parent (even if you ask for it :-| ). Request org_unit details.
                org_unit = self._request.get('organisationUnits/' + org_unit['id'])
                while True:
                    if not org_unit.get('parent'):
                        # The organisation unit with no parent is the top-most organisation unit
                        break
                    org_unit = self._request.get('organisationUnits/' + org_unit['parent']['id'])
                self._top_org_unit = org_unit
        return self._top_org_unit

    def get_resource_id(self, resource, name):
        """
        Returns the ID of the given resource type with the given name
        """
        response = self._request.get(resource, params={'links': 'false', 'query': name})
        if not response[resource]:
            return None
        if len(response[resource]) > 1:
            raise Dhis2ApiQueryError('Query returned multiple results')
        return response[resource][0]['id']

    def get_program_id(self, name):
        """
        Returns the ID of the given program
        """
        return self.get_resource_id('programs', name)

    def get_program_stage_id(self, name):
        """
        Returns the ID of the given program stage
        """
        return self.get_resource_id('programStages', name)

    def get_te_id(self, name):
        """
        Returns the ID of the given tracked entity type
        """
        return self.get_resource_id('trackedEntities', name)

    def get_te_attr_id(self, name):
        """
        Returns the ID of the given tracked entity attribute
        """
        if name not in self._tracked_entity_attributes:
            # Note: self.get_resource_id returns None if name not found
            self._tracked_entity_attributes[name] = self.get_resource_id('trackedEntityAttributes', name)
        return self._tracked_entity_attributes[name]

    def get_te_inst(self, te_inst_id):
        """
        Return the tracked entity instance identified by the give ID
        """
        inst = self._request.get('trackedEntityInstances/' + te_inst_id)
        instance = {attr['displayName']: attr['value'] for attr in inst['attributes']}
        instance.update({
            'Instance': inst['trackedEntityInstance'],
            'Tracked entity': inst['trackedEntity'],
            'Org unit': inst['orgUnit'],
        })
        return instance

    def gen_instances_with_unset(self, te_name, attr_name):
        """
        Returns a list of tracked entity instances with the given attribute name unset
        """
        top_ou = self.get_top_org_unit()
        te_id = self.get_te_id(te_name)
        attr_id = self.get_te_attr_id(attr_name)
        page = 1
        while True:
            # Because we don't have an "UNSET" filter, we need to fetch all and yield the unset ones
            response = self._request.get(
                'trackedEntityInstances',
                params={
                    'paging': 'true',
                    'page': page,
                    'links': 'false',
                    'trackedEntity': te_id,
                    'ou': top_ou['id'],
                    'ouMode': 'DESCENDANTS',
                    'attribute': attr_id
                })
            instances = self.entities_to_dicts(response)
            for inst in instances:
                if not inst.get(attr_name):
                    yield inst
            if page < response['metaData']['pager']['pageCount']:
                page += 1
            else:
                break

    def gen_instances_with_equals(self, te_name, attr_name, attr_value):
        """
        Yields tracked entity instances with the given attribute set to the given value
        """
        top_ou = self.get_top_org_unit()
        te_id = self.get_te_id(te_name)
        attr_id = self.get_te_attr_id(attr_name)
        if attr_id is None:
            raise Dhis2ConfigurationError(
                'DHIS2 tracked entity attribute name "%s" unknown on host "%s"',
                attr_name, self._request.baseurl)
        page = 1
        while True:
            response = self._request.get(
                'trackedEntityInstances',
                params={
                    'paging': 'true',
                    'page': page,
                    'links': 'false',
                    'trackedEntity': te_id,
                    'ou': top_ou['id'],
                    'ouMode': 'DESCENDANTS',
                    'attribute': attr_id + ':EQ:' + attr_value
                })
            instances = self.entities_to_dicts(response)
            for inst in instances:
                yield inst
            if page < response['metaData']['pager']['pageCount']:
                page += 1
            else:
                break

    def gen_instances_in_program(self, program):
        """
        Yields tracked entity instances enrolled in the given program
        """
        top_ou = self.get_top_org_unit()
        program_id = self.get_program_id(program)
        page = 1
        while True:
            response = self._request.get(
                'trackedEntityInstances',
                params={
                    'paging': 'true',
                    'page': page,
                    'links': 'false',
                    'ou': top_ou['id'],
                    'ouMode': 'DESCENDANTS',
                    'program': program_id
                })
            instances = self.entities_to_dicts(response)
            for inst in instances:
                yield inst
            if page < response['metaData']['pager']['pageCount']:
                page += 1
            else:
                break

    def gen_org_units(self):
        """
        Yields organisation units
        """
        page = 1
        while True:
            response = self._request.get(
                'organisationUnits',
                params={
                    'paging': 'true',
                    'pageSize': 500,
                    'page': page,
                    'links': 'false'
                })
            for org_unit in response['organisationUnits']:
                yield org_unit
            if page < response['pager']['pageCount']:
                page += 1
            else:
                break

    def gen_org_units_with_parents(self):
        """
        Yields organisation units with parent IDs
        """
        # TODO: Use a SQL query.
        # cf. https://www.dhis2.org/doc/snapshot/en/user/html/ch25s21.html
        for ou in self.gen_org_units():
            ou['parent_id'] = self.get_org_unit_parent_id(ou['id'])
            yield ou

    def get_org_unit_parent_id(self, ou_id):
        details = self._request.get('organisationUnits/' + ou_id)
        return details['parent']['id'] if details.get('parent') else None

    def enroll_in(self, te_inst_id, program, when=None, data=None):
        """
        Enroll the given tracked entity instance in the given program

        :param te_inst_id: The ID of a tracked entity instance
        :param program: The *name* of a program
        :param when: The date ("YYYY-MM-DD") of enrollment. Defaults to today.
        :param data: Dictionary of additional data values of event.
        :return: The API response
        """
        program_id = self.get_resource_id('programs', program)
        return self.enroll_in_id(te_inst_id, program_id, when, data)

    def enroll_in_id(self, te_inst_id, program_id, when=None, data=None):
        """
        Enroll the given tracked entity instance in the given program

        :param te_inst_id: The ID of a tracked entity instance
        :param program_id: The ID of a program
        :param when: The date ("YYYY-MM-DD") of enrollment. Defaults to today.
        :param data: Dictionary of additional data values of event.
        :return: The API response
        """
        # cf. https://www.dhis2.org/doc/snapshot/en/user/html/ch31s34.html
        if when is None:
            when = date.today()
        request_data = {
            "trackedEntityInstance": te_inst_id,
            "program": program_id,
            "dateOfEnrollment": when,
            "dateOfIncident": when
        }
        if data:
            request_data['attributes'] = self._data_to_attributes(data)
        return self._request.post('enrollments', request_data)

    def enrolled_in(self, te_inst_id, program):
        """
        Checks whether a given tracked entity instance is enrolled in a given
        program

        :param te_inst_id: The ID of a tracked entity instance
        :param program: The name of a program
        :return: boolean
        """
        # TODO: Instead of iterating instances, maybe use a SQL query.
        # cf. https://www.dhis2.org/doc/snapshot/en/user/html/ch25s21.html
        return any(inst['Instance'] == te_inst_id for inst in self.gen_instances_in_program(program))

    def _get_event_data_values(self, xform, data_element_names):
        """
        Return event dataElement-value pairs.

        The data_element_names map caters for both a simple mapping, and
        mapping dropdown field-value tuples to DHIS2 boolean dataElements. See
        RISK_ASSESSMENT_EVENT_FIELDS for an example.
        """
        # data_values = [{
        #     'dataElement': self._data_elements[element_name],
        #     'value': xform.form[field_name],
        # } for field_name, element_name in data_element_names.iteritems() if field_name in xform.form]
        data_values = []
        for field, element_name in data_element_names.iteritems():
            if isinstance(field, tuple):
                # field is (field_name, field_value) where field_value is one of many checkboxes
                field_name, field_value = field
                # e.g. xform.form['multi-select_field'] == 'checkbox_one checkbox_two checkbox_five'
                if field_value in xform.form.get(field_name, '').split():
                    data_values.append({
                        'dataElement': self._data_elements[element_name],
                        'value': True
                    })
            else:
                if field in xform.form:
                    data_values.append({
                        'dataElement': self._data_elements[element_name],
                        'value': xform.form[field]
                    })
        return data_values

    def form_to_event(self, program_id, xform, data_element_names, program_stage_id=None, te_inst_id=None):
        """
        Builds a dict representing a DHIS2 event

        :param program_id: The program can't be determined from form data.
        :param xform: An XFormInstance
        :param data_element_names: A dictionary mapping CCHQ form field names
                                   to DHIS2 tracked entity attribute names
        :param program_stage_id: Program stage for programs with stages
        :param te_inst_id: Tracked entity instance ID, for creating an event
                           with registration

        An example of an event: ::

            {
              "program": "eBAyeGv0exc",
              "orgUnit": "DiszpKrYNg8",
              "eventDate": "2013-05-17",
              "status": "COMPLETED",
              "storedBy": "admin",
              "coordinate": {
                "latitude": "59.8",
                "longitude": "10.9"
              },
              "dataValues": [
                { "dataElement": "qrur9Dvnyt5", "value": "22" },
                { "dataElement": "oZg33kd9taw", "value": "Male" },
                { "dataElement": "msodh3rEMJa", "value": "2013-05-18" }
              ]
            }

        See the DHIS2 `Events documentation`_ for more information.


        .. _Events documentation: https://www.dhis2.org/doc/snapshot/en/user/html/ch28s09.html

        """
        # For more information on the data to be sent from CCHQ to DHIS2, see
        # README.rst. Required data is given in 4.3 of the Specification
        if any(e not in self._data_elements for e in data_element_names.values()):
            self._fetch_data_elements()

        if xform.form.get('dhis_org_id'):
            org_unit = xform.form['dhis_org_id']
        else:
            case_id = xform.form['case']['@case_id']
            case = CommCareCase.get(case_id)
            if getattr(case, 'dhis_org_id', None):
                org_unit = case['dhis_org_id']
            else:
                # The case doesn't have an org unit.
                return
        event = {
            'program': program_id,
            'orgUnit': org_unit,
            'eventDate': xform.received_on.date(),
            'status': 'COMPLETED',
            'storedBy': self._username,
            'dataValues': self._get_event_data_values(xform, data_element_names)
        }
        if program_stage_id:
            event['programStage'] = program_stage_id
        if te_inst_id:
            event['trackedEntityInstance'] = te_inst_id
        if xform.metadata.location:
            event['coordinate'] = {
                'latitude': xform.metadata.location.latitude,
                'longitude': xform.metadata.location.longitude,
            }
        return event

    def send_events(self, events):
        """
        Send events to the DHIS2 API.

        :param events: A dictionary of an event or an eventList.

        See DHIS2 `Events documentation`_ for details.


        .. _Events documentation: https://www.dhis2.org/doc/snapshot/en/user/html/ch28s09.html
        """
        return self._request.post('events', events)

    @staticmethod
    def entities_to_dicts(response):
        """
        Parse the list of lists returned by a DHIS2 API entity request,
        and return it as a list of dictionaries.

        The DHIS2 API returns entity instances with a list of headers, and
        then a list of lists, as if it was dumping a spreadsheet. e.g. ::

            {
                'headers': [
                    {
                        'name': 'instance',
                        'column': 'Instance',
                        'type': 'java.lang.String',
                        'hidden': False,
                        'meta': False
                    },
                    {
                        'name': 'ou',
                        'column': 'Org unit',
                        'type': 'java.lang.String',
                        'hidden': False,
                        'meta': False
                    },
                    {
                        'name': 'dv3nChNSIxy',
                        'column': 'First name',
                        'type': 'java.lang.String',
                        'hidden': False,
                        'meta': False
                    },
                    {
                        'name': 'hwlRTFIFSUq',
                        'column': 'Last name',
                        'type': 'java.lang.String',
                        'hidden': False,
                        'meta': False
                    }
                ],
                'rows': [
                    [
                        'GpetderUTA7',
                        'Qw7c6Ckb0XC',
                        'Tesmi',
                        'Petros'
                    ],
                    [
                        'LTxvKtKq48t',
                        'Qw7c6Ckb0XC',
                        'Luwam',
                        'Rezene'
                    ],
                ]
            }

        Header "name" values like "dv3nChNSIxy" and "hwlRTFIFSUq" are not
        friendly, and so the returned dictionary uses the "column" value
        as key. The return value for this example would be ::

            [
                {
                    'Instance': 'GpetderUTA7',
                    'Org unit': 'Qw7c6Ckb0XC',
                    'First name: 'Tesmi',
                    'Last name': 'Petros'
                },
                {
                    'Instance': 'LTxvKtKq48t',
                    'Org unit': 'Qw7c6Ckb0XC',
                    'First name: 'Luwam',
                    'Last name': 'Rezene'
                }
            ]

        The row value of "Tracked entity" will look like "cyl5vuJ5ETQ".
        This isn't very friendly either. But the entity name is given in
        "metaData", which looks like this: ::

            "metaData": {
                "pager": {
                    "page": 1,
                    "total": 50,
                    "pageSize": 50,
                    "pageCount": 1
                },
                "names": {
                    "cyl5vuJ5ETQ": "Person"
                }
            }

        So we look up tracked entity names, and include them in the dictionary.

        """
        entities = []
        for row in response['rows']:
            entity = {}
            for i, item in enumerate(row):
                if response['headers'][i]['column'] == 'Tracked entity':
                    # Look up the name of the tracked entity
                    item = response['metaData']['names'][item]
                entity[response['headers'][i]['column']] = item
            entities.append(entity)
        return entities


class FixtureManagerError(Exception):
    pass


def to_field_list(value):
    """
    Return a field value as a FieldList
    """
    return FieldList(field_list=[FixtureItemField(field_value=value, properties={})])


def to_field_value(field_list):
    """
    Return the first field value in a FieldList
    """
    try:
        return field_list.field_list[0].field_value
    except IndexError:
        return None


class FixtureManager(object):
    """
    Reuses the Django manager pattern for fixtures
    """

    def __init__(self, model_class, domain, tag):
        self.model_class = model_class
        self.domain = domain
        self.tag = tag

    def get(self, fixture_id):
        item = FixtureDataItem.get(fixture_id)
        fields = {k: to_field_value(v) for k, v in item.fields.iteritems()}
        return self.model_class(_fixture_id=item.get_id, **fields)

    def all(self):
        for item in FixtureDataItem.get_item_list(self.domain, self.tag):
            fields = {k: to_field_value(v) for k, v in item.fields.iteritems()}
            yield self.model_class(_fixture_id=item.get_id, **fields)


class Dhis2OrgUnit(object):
    """
    Simplify the management of DHIS2 Organisation Units, which are
    stored in a lookup table.
    """

    # The manager is set outside of the class definition so that we can pass
    # the class to the manager
    objects = None

    def __init__(self, id, name, parent_id, _fixture_id=None):
        # It's not nice to shadow the "id" built-in, but naming the param "id"
        # allows us to pass values in from CouchDB as kwargs with less fuss.
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self._fixture_id = _fixture_id

    def get_id(self):
        # Pity we've got an attribute called "id" that isn't our REAL ID. This
        # returns the fixture ID.
        return self._fixture_id

    def save(self):
        if self.objects is None:
            raise FixtureManagerError(
                'FixtureManager not set. '
                'e.g. `Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, domain, ORG_UNIT_FIXTURES)`')
        data_type = FixtureDataType.by_domain_tag(self.objects.domain, self.objects.tag).one()
        if data_type is None:
            raise Dhis2ConfigurationError(
                'Unable to find lookup table in domain "%s" with ID "%s".' %
                (self.objects.domain, self.objects.tag))
        data_item = FixtureDataItem(
            data_type_id=data_type.get_id,
            domain=self.objects.domain,
            fields={
                'id': to_field_list(self.id),
                'name': to_field_list(self.name),
                'parent_id': to_field_list(self.parent_id)
            })
        data_item.save()
        self._fixture_id = data_item.get_id
        return self._fixture_id

    def delete(self):
        if self._fixture_id is None:
            return
        item = FixtureDataItem.get(self._fixture_id)
        item.delete()

# To use Dhis2OrgUnit with FixtureManager, create a manager instance, and use
# it to fetch org units. You need to do it at runtime in order to create your
# FixtureManager instance with the right domain. e.g.:
#     Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, domain, ORG_UNIT_FIXTURES)
#     our_org_units = {ou.id: ou for ou in Dhis2OrgUnit.objects.all()}
