from xml.etree import ElementTree
from corehq.apps.users.models import CommCareUser
from couchdbkit.ext.django.schema import Document, DictProperty, StringProperty, StringListProperty
from corehq.apps.groups.models import Group
from dimagi.utils.couch.database import get_db

class FixtureTypeCheckError(Exception):
    pass

class FixtureDataType(Document):
    domain = StringProperty()
    tag = StringProperty()
    name = StringProperty()
    fields = StringListProperty()

class FixtureDataItem(Document):
    domain = StringProperty()
    data_type_id = StringProperty()
    fields = DictProperty()

    @property
    def data_type(self):
        if not hasattr(self, '_data_type'):
            self._data_type = FixtureDataType.get(self.data_type_id)
        return self._data_type

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
            xField.text = self.fields[field] if self.fields.has_key(field) else ""
        return xData

    def get_users(self, wrap=True):
        user_ids = set(
            get_db().view('fixtures/ownership',
                key=['user by data_item', self.domain, self.get_id],
                reduce=False,
                wrapper=lambda r: r['value']
            )
        )
        group_ids = set(
            get_db().view('fixtures/ownership',
                key=['group by data_item', self.domain, self.get_id],
                reduce=False,
                wrapper=lambda r: r['value']
            )
        )
        users_in_groups = [group.get_users(only_commcare=True) for group in Group.view('_all_docs', keys=list(group_ids))]
        if wrap:
            return set(CommCareUser.view('_all_docs', keys=list(user_ids))) | set(users_in_groups)
        else:
            return user_ids | set([user.get_id for user in users_in_groups])

    @classmethod
    def by_user(cls, user, wrap=True):
        group_ids = Group.by_user(user, wrap=False)

        fixture_ids = set(
            get_db().view('fixtures/ownership',
                key=['data_item by user', user.domain, user.user_id] + [['data_item by group', user.domain, group_id] for group_id in group_ids],
                reduce=False,
                wrapper=lambda r: r['value'],
            )
        )
        if wrap:
            return cls.view('_all_docs', keys=list(fixture_ids))
        else:
            return fixture_ids

class FixtureOwnership(Document):
    domain = StringProperty()
    data_item_id = StringProperty()
    owner_id = StringProperty()
    owner_type = StringProperty(choices=['user', 'group'])