from corehq.apps.object_testing.framework.forms import RawJSONForm


class RawJSON:
    form_class = RawJSONForm

    def __init__(self, data):
        self.data = data

    def get_context(self):
        form = self.form_class(self.data)
        if form.is_valid():
            return self.get_context_from_cleaned_data(form.cleaned_data)
        else:
            raise Exception(form.errors)

    def get_context_from_cleaned_data(self, cleaned_data):
        return cleaned_data["raw_json"]


class ContextFactor:
    mapping = {
        'raw': RawJSON
    }

    @classmethod
    def get_factory(cls, slug, data):
        factory_cls = cls.mapping[slug]
        return factory_cls(data)
