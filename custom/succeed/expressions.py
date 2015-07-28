from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject


class ReferencedIdExpressionSpec(JsonObject):
    type = TypeProperty('succeed_referenced_id')

    def __call__(self, item, context=None):
        try:
            return item['indices'][0]['referenced_id']
        except KeyError:
            return None


def succeed_referenced_id(spec, context):
    wrapped = ReferencedIdExpressionSpec.wrap(spec)
    return wrapped
