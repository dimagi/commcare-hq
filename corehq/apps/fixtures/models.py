from xml.etree import ElementTree
from corehq.apps.users.models import CommCareUser
from couchdbkit.ext.django.schema import Document, DictProperty, StringProperty, StringListProperty
from corehq.apps.groups.models import Group
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.couch.database import get_db

class FixtureTypeCheckError(Exception):
    pass

class FixtureDataType(Document):
    domain = StringProperty()
    tag = StringProperty()
    name = StringProperty()
    fields = StringListProperty()

    @classmethod
    def by_domain(cls, domain):
        return cls.view('fixtures/data_types_by_domain', key=domain, reduce=False, include_docs=True)

    @classmethod
    def by_domain_tag(cls, domain, tag):
        return cls.view('fixtures/data_types_by_domain_tag', key=[domain, tag], reduce=False, include_docs=True)

    def recursive_delete(self, transaction):
        item_ids = []
        for item in FixtureDataItem.by_data_type(self.domain, self.get_id):
            transaction.delete(item)
            item_ids.append(item.get_id)
        transaction.delete_all(FixtureOwnership.for_all_item_ids(item_ids, self.domain))
        transaction.delete(self)

class FixtureDataItem(Document):
    domain = StringProperty()
    data_type_id = StringProperty()
    fields = DictProperty()

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
            ownership.delete()

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
            if field in fields:
                fields.remove(field)
            else:
                raise FixtureTypeCheckError("field %s not in fixture data %s" % (field, self.get_id))
        if fields:
            raise FixtureTypeCheckError("fields %s from fixture data %s not in fixture data type" % (', '.join(fields), self.get_id))

    def to_xml(self):
        xData = ElementTree.Element(self.data_type.tag)
        for field in self.data_type.fields:
            xField = ElementTree.SubElement(xData, field)
            xField.text = unicode(self.fields[field]) if self.fields.has_key(field) else ""
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
        ).all()

        return cls.view('_all_docs', keys=list(fixture_ids), include_docs=True) if wrap else fixture_ids

    @classmethod
    def by_data_type(cls, domain, data_type):
        data_type_id = _id_from_doc(data_type)
        return cls.view('fixtures/data_items_by_domain_type', key=[domain, data_type_id], reduce=False, include_docs=True)

    @classmethod
    def by_domain(cls, domain):
        return cls.view('fixtures/data_items_by_domain_type', startkey=[domain], endkey=[domain, {}], reduce=False, include_docs=True)

    @classmethod
    def by_field_value(cls, domain, data_type, field_name, field_value):
        data_type_id = _id_from_doc(data_type)
        return cls.view('fixtures/data_items_by_field_value', key=[domain, data_type_id, field_name, field_value],
                        reduce=False, include_docs=True)

    def delete_ownerships(self, transaction):
        ownerships = FixtureOwnership.by_item_id(self.get_id, self.domain)
        transaction.delete_all(ownerships)

    def delete_recursive(self, transaction):
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