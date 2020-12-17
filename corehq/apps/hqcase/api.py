import uuid

import jsonobject

from casexml.apps.case.mock import CaseBlock


def is_simple_dict(d):
    if not isinstance(d, dict) or not all(
            isinstance(v, str) for v in d.values()
    ):
        raise jsonobject.BadValueError()


class JsonCaseCreation(jsonobject.JsonObject):
    case_type = jsonobject.StringProperty(name='@case_type', required=True)
    case_name = jsonobject.StringProperty(name='@case_name', required=True)
    user_id = jsonobject.StringProperty(required=True)
    owner_id = jsonobject.StringProperty(name='@owner_id', required=True)
    properties = jsonobject.DictProperty(validators=[is_simple_dict], default={})

    _allow_dynamic_properties = False

    class Meta(object):
        # prevent JsonObject from auto-converting dates etc.
        string_conversions = ()

    def get_caseblock(self):
        return CaseBlock(
            case_id=str(uuid.uuid4()),
            user_id=self.user_id,
            case_type=self.case_type,
            case_name=self.case_name,
            owner_id=self.owner_id,
            create=True,
            update=dict(self.properties),
            external_id=self.properties.get('external_id', CaseBlock.undefined),
        ).as_text()
