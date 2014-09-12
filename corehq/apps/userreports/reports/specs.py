from jsonobject import JsonObject, StringProperty, BooleanProperty, ListProperty


class FilterChoice(JsonObject):
    value = StringProperty(required=True)
    display = StringProperty()

    def get_display(self):
        return self.display or self.value


class FilterSpec(JsonObject):
    slug = StringProperty(required=True)
    display = StringProperty()
    required = BooleanProperty(default=False)

    def get_display(self):
        return self.display or self.slug

class ChoiceListFilterSpec(FilterSpec):
    choices = ListProperty(FilterChoice)
