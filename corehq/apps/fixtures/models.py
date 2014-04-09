import warnings 

from xml.etree import ElementTree
from couchdbkit.exceptions import ResourceNotFound, ResourceConflict
from corehq.apps.fixtures.exceptions import FixtureException
from corehq.apps.users.models import CommCareUser
from corehq.apps.fixtures.exceptions import FixtureVersionError
from couchdbkit.ext.django.schema import Document, DocumentSchema, DictProperty, StringProperty, StringListProperty, SchemaListProperty, IntegerProperty, BooleanProperty
from corehq.apps.groups.models import Group
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.couch.database import get_db


class FixtureTypeField(DocumentSchema):
    field_name = StringProperty()
    properties = StringListProperty()


class FixtureDataType(Document):
    domain = StringProperty()
    is_global = BooleanProperty(default=False)
    tag = StringProperty()
    fields = SchemaListProperty(FixtureTypeField)

    @classmethod
    def wrap(cls, obj):
        if obj["fields"] and isinstance(obj['fields'][0], basestring):
            obj['fields'] = [{'field_name': f, 'properties': []} for f in obj['fields']]
        return super(FixtureDataType, cls).wrap(obj)

    # support for old fields
    @property
    def fields_without_attributes(self):
        fields_without_attributes = []
        for fixt_field in self.fields:
            fields_without_attributes.append(fixt_field.field_name)
        return fields_without_attributes

    @classmethod
    def total_by_domain(cls, domain):
        num_fixtures = FixtureDataType.get_db().view(
            'fixtures/data_types_by_domain',
            reduce=True,
            key=domain,
        ).first()
        return num_fixtures['value'] if num_fixtures is not None else 0

    @classmethod
    def by_domain(cls, domain):
        return cls.view('fixtures/data_types_by_domain', key=domain, reduce=False, include_docs=True, descending=True)

    @classmethod
    def by_domain_tag(cls, domain, tag):
        return cls.view('fixtures/data_types_by_domain_tag', key=[domain, tag], reduce=False, include_docs=True, descending=True)

    @classmethod
    def fixture_tag_exists(cls, domain, tag):
        fdts = FixtureDataType.by_domain(domain)
        for fdt in fdts:
            if tag == fdt.tag:
                return fdt
        return False

    def recursive_delete(self, transaction):
        item_ids = []
        for item in FixtureDataItem.by_data_type(self.domain, self.get_id):
            transaction.delete(item)
            item_ids.append(item.get_id)
        transaction.delete_all(FixtureOwnership.for_all_item_ids(item_ids, self.domain))
        transaction.delete(self)

    @classmethod
    def delete_fixtures_by_domain(cls, domain, transaction):
        for type in FixtureDataType.by_domain(domain):
            type.recursive_delete(transaction)


class FixtureItemField(DocumentSchema):
    """
        "field_value": "Delhi_IN_HIN",
        "properties": {"lang": "hin"} 
    """
    field_value = StringProperty()
    properties = DictProperty()


class FieldList(DocumentSchema):
    """
        List of fields for different combinations of properties
    """
    field_list = SchemaListProperty(FixtureItemField)


class FixtureDataItem(Document):
    """
    Example old Item:
        domain = "hq-domain"
        data_type_id = <id of state FixtureDataType>
        fields = {
            "country": "India",
            "state_name": "Delhi",
            "state_id": "DEL"
        }

    Example new Item with attributes:
        domain = "hq-domain"
        data_type_id = <id of state FixtureDataType>
        fields = {
            "country": {"field_list": [
                {"field_value": "India", "properties": {}},
            ]},
            "state_name": {"field_list": [
                {"field_value": "Delhi_IN_ENG", "properties": {"lang": "eng"}},
                {"field_value": "Delhi_IN_HIN", "properties": {"lang": "hin"}},                
            ]},
            "state_id": {"field_list": [
                {"field_value": "DEL", "properties": {}}
            ]}
        }
    If one of field's 'properties' is an empty 'dict', the field has no attributes
    """
    domain = StringProperty()
    data_type_id = StringProperty()
    fields = DictProperty(FieldList)
    sort_key = IntegerProperty()

    @classmethod
    def wrap(cls, obj):
        if not obj["fields"]:
            return super(FixtureDataItem, cls).wrap(obj)
        
        is_of_new_type = False
        fields_dict = {}        
        for field in obj['fields']:
            if obj['fields'][field] is not None and not isinstance(obj['fields'][field], basestring):
                is_of_new_type = True
                break
            fields_dict[field] = {
                "field_list": [
                    {
                        'field_value': obj['fields'][field],
                        'properties': {}
                    }
                ]
            }
        if not is_of_new_type:
            obj['fields'] = fields_dict
        return super(FixtureDataItem, cls).wrap(obj)

    @property
    def fields_without_attributes(self):
        fields = {}
        for field in self.fields:
            # if the field has properties, a unique field_val can't be generated for FixtureItem
            if len(self.fields[field].field_list) > 1:
                raise FixtureVersionError("This method is not supported for fields with properties."
                                          " field '%s' has properties" % field)
            fields[field] = self.fields[field].field_list[0].field_value
        return fields

    @property
    def data_type(self):
        if not hasattr(self, '_data_type'):
            self._data_type = FixtureDataType.get(self.data_type_id)
        return self._data_type

    def add_owner(self, owner, owner_type, transaction=None):
        assert(owner.domain == self.domain)
        with transaction or CouchTransaction() as transaction:
            o = FixtureOwnership(domain=self.domain, owner_type=owner_type, owner_id=owner.get_id, data_item_id=self.get_id)
            transaction.save(o)
        return o

    def remove_owner(self, owner, owner_type):
        for ownership in FixtureOwnership.view('fixtures/ownership',
            key=[self.domain, 'by data_item and ' + owner_type, self.get_id, owner.get_id],
            reduce=False,
            include_docs=True
        ):
            try:
                ownership.delete()
            except ResourceNotFound:
                # looks like it was already deleted
                pass
            except ResourceConflict:
                raise FixtureException((
                    "couldn't remove ownership {owner_id} for item {fixture_id} of type "
                    "{data_type_id} in domain {domain}. It was updated elsewhere"
                ).format(
                    owner_id=ownership._id,
                    fixture_id=self._id,
                    data_type_id=self.data_type_id,
                    domain=self.domain
                ))

    def add_user(self, user, transaction=None):
        return self.add_owner(user, 'user', transaction=transaction)

    def remove_user(self, user):
        return self.remove_owner(user, 'user')

    def add_group(self, group, transaction=None):
        return self.add_owner(group, 'group', transaction=transaction)

    def remove_group(self, group):
        return self.remove_owner(group, 'group')

    def type_check(self):
        fields = set(self.fields.keys())
        for field in self.data_type.fields:
            if field.field_name in fields:
                fields.remove(field)
            else:
                raise FixtureTypeCheckError("field %s not in fixture data %s" % (field.field_name, self.get_id))
        if fields:
            raise FixtureTypeCheckError("fields %s from fixture data %s not in fixture data type" % (', '.join(fields), self.get_id))

    def to_xml(self):
        xData = ElementTree.Element(self.data_type.tag)
        for field in self.data_type.fields:
            if not self.fields.has_key(field.field_name):
                xField = ElementTree.SubElement(xData, field.field_name)
                xField.text = ""
            else:
                for field_with_attr in self.fields[field.field_name].field_list:
                    xField = ElementTree.SubElement(xData, field.field_name)
                    xField.text = field_with_attr.field_value or ""
                    for attribute in field_with_attr.properties:
                        xField.attrib[attribute] = field_with_attr.properties[attribute]
        return xData

    def get_groups(self, wrap=True):
        group_ids = set(
            get_db().view('fixtures/ownership',
                key=[self.domain, 'group by data_item', self.get_id],
                reduce=False,
                wrapper=lambda r: r['value']
            )
        )
        if wrap:
            return set(Group.view('_all_docs', keys=list(group_ids), include_docs=True))
        else:
            return group_ids

    def get_users(self, wrap=True, include_groups=False):
        user_ids = set(
            get_db().view('fixtures/ownership',
                key=[self.domain, 'user by data_item', self.get_id],
                reduce=False,
                wrapper=lambda r: r['value']
            )
        )
        if include_groups:
            group_ids = self.get_groups(wrap=False)
        else:
            group_ids = set()
        users_in_groups = [group.get_users(only_commcare=True) for group in Group.view('_all_docs',
            keys=list(group_ids),
            include_docs=True
        )]
        if wrap:
            return set(CommCareUser.view('_all_docs', keys=list(user_ids), include_docs=True)).union(*users_in_groups)
        else:
            return user_ids | set([user.get_id for user in users_in_groups])

    def get_all_users(self, wrap=True):
        return self.get_users(wrap=wrap, include_groups=True)

    @classmethod
    def by_user(cls, user, wrap=True, domain=None):
        group_ids = Group.by_user(user, wrap=False)

        if isinstance(user, dict):
            user_id = user.get('user_id')
            user_domain = domain
        else:
            user_id = user.user_id
            user_domain = user.domain

        fixture_ids = set(
            FixtureOwnership.get_db().view('fixtures/ownership',
                keys=[[user_domain, 'data_item by user', user_id]] + [[user_domain, 'data_item by group', group_id] for group_id in group_ids],
                reduce=False,
                wrapper=lambda r: r['value'],
            )
        )
        if wrap:
            results = cls.get_db().view('_all_docs', keys=list(fixture_ids), include_docs=True)

            # sort the results into those corresponding to real documents
            # and those corresponding to deleted or non-existent documents
            docs = []
            deleted_fixture_ids = set()

            for result in results:
                if result.get('doc'):
                    docs.append(cls.wrap(result['doc']))
                elif result.get('error'):
                    assert result['error'] == 'not_found'
                    deleted_fixture_ids.add(result['key'])
                else:
                    assert result['value']['deleted'] is True
                    deleted_fixture_ids.add(result['id'])

            # fetch and delete ownership documents pointing
            # to deleted or non-existent fixture documents
            # this cleanup is necessary since we used to not do this
            bad_ownerships = FixtureOwnership.for_all_item_ids(deleted_fixture_ids, user_domain)
            FixtureOwnership.get_db().bulk_delete(bad_ownerships)

            return docs
        else:
            return fixture_ids

    @classmethod
    def by_group(cls, group, wrap=True):
        fixture_ids = get_db().view('fixtures/ownership',
            key=[group.domain, 'data_item by group', group.get_id],
            reduce=False,
            wrapper=lambda r: r['value'],
            descending=True
        ).all()

        return cls.view('_all_docs', keys=list(fixture_ids), include_docs=True) if wrap else fixture_ids

    @classmethod
    def by_data_type(cls, domain, data_type):
        data_type_id = _id_from_doc(data_type)
        return cls.view('fixtures/data_items_by_domain_type', key=[domain, data_type_id], reduce=False, include_docs=True, descending=True)

    @classmethod
    def by_domain(cls, domain):
        return cls.view('fixtures/data_items_by_domain_type', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True, descending=True)

    @classmethod
    def by_field_value(cls, domain, data_type, field_name, field_value):
        data_type_id = _id_from_doc(data_type)
        return cls.view('fixtures/data_items_by_field_value', key=[domain, data_type_id, field_name, field_value],
                        reduce=False, include_docs=True)

    @classmethod
    def get_item_list(cls, domain, tag):
        data_type = FixtureDataType.by_domain_tag(domain, tag).one()
        return cls.by_data_type(domain, data_type).all()

    @classmethod
    def get_indexed_items(cls, domain, tag, index_field):
        """
        Looks up an item list and converts to mapping from `index_field`
        to a dict of all fields for that item.

            fixtures = FixtureDataItem.get_indexed_items('my_domain',
                'item_list_tag', 'index_field')
            result = fixtures['index_val']['result_field']
        """
        fixtures = cls.get_item_list(domain, tag)
        return dict((f.fields_without_attributes[index_field], f.fields_without_attributes) for f in fixtures)

    def delete_ownerships(self, transaction):
        ownerships = FixtureOwnership.by_item_id(self.get_id, self.domain)
        transaction.delete_all(ownerships)

    def recursive_delete(self, transaction):
        self.delete_ownerships(transaction)
        transaction.delete(self)


def _id_from_doc(doc_or_doc_id):
    if isinstance(doc_or_doc_id, basestring):
        doc_id = doc_or_doc_id
    else:
        doc_id = doc_or_doc_id.get_id if doc_or_doc_id else None
    return doc_id


class FixtureOwnership(Document):
    domain = StringProperty()
    data_item_id = StringProperty()
    owner_id = StringProperty()
    owner_type = StringProperty(choices=['user', 'group'])

    @classmethod
    def by_item_id(cls, item_id, domain):
        ownerships = cls.view('fixtures/ownership',
            key=[domain, 'by data_item', item_id],
            include_docs=True,
            reduce=False,
        ).all()

        return ownerships

    @classmethod
    def for_all_item_ids(cls, item_ids, domain):
        ownerships = FixtureOwnership.view('fixtures/ownership',
            keys=[[domain, 'by data_item', item_id] for item_id in item_ids],
            include_docs=True,
            reduce=False
        ).all()

        return ownerships
