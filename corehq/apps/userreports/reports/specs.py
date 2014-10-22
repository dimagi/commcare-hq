from jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty
from corehq.apps.userreports.specs import TypeProperty


class FilterChoice(JsonObject):
    value = StringProperty(required=True)
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    """
    This is the spec for a report filter - a thing that should show up as a UI filter element
    in a report (like a date picker or a select list).
    """
    slug = StringProperty(required=True)  # this shows up as the ID in the filter HTML
    field = StringProperty(required=True)  # this is the actual column that is queried
    display = StringProperty()
    required = BooleanProperty(default=False)

    def get_display(self):
        return self.display or self.slug


class ChoiceListFilterSpec(FilterSpec):
    type = TypeProperty('choice_list')
    choices = ListProperty(FilterChoice)
