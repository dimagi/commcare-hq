from jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty


class FilterChoice(JsonObject):
    value = StringProperty(required=True)
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    slug = StringProperty(required=True)  # this shows up as the ID in the filter HTML
    field = StringProperty(required=True)  # this is the actual column that is queried
    display = StringProperty()
    required = BooleanProperty(default=False)

    def get_display(self):
        return self.display or self.slug

class ChoiceListFilterSpec(FilterSpec):
    choices = ListProperty(FilterChoice)
