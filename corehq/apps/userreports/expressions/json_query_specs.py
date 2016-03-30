from dimagi.ext.jsonobject import JsonObject, DictProperty
from corehq.apps.userreports.specs import TypeProperty


class FilterItemsExpressionSpec(JsonObject):
    type = TypeProperty('filter_items')
    items_expression = DictProperty(required=True)
    filter_expression = DictProperty(required=True)

    def configure(self, items_expression, filter_expression):
        self._items_expression = items_expression
        self._filter_expression = filter_expression

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []

        values = []
        for item in items:
            if self._filter_expression(item, context):
                values.append(item)

        return values
