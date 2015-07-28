from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject


class ReferencedIdExpressionSpec(JsonObject):
    type = TypeProperty('succeed_referenced_id')

    def __call__(self, item, context=None):
        referenced_id = item['indices'][0]['referenced_id']
        return referenced_id


class FullNameExpressionSpec(JsonObject):
    type = TypeProperty('succeed_full_name')

    def __call__(self, item, context=None):
        referenced_id = item['indices'][0]['referenced_id']
        try:
            return CommCareCase.get(referenced_id)['full_name']
        except AttributeError:
            return None


def succeed_full_name(spec, context):
    wrapped = FullNameExpressionSpec.wrap(spec)
    return wrapped


def succeed_referenced_id(spec, context):
    wrapped = ReferencedIdExpressionSpec.wrap(spec)
    return wrapped
