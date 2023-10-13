from corehq.apps.object_testing.framework.forms import RawJSONForm


VALUE_KEY = "__value__"


class RawJSON:
    form_class = RawJSONForm

    def get_context(self, data):
        data = {"raw_json": wrap_plain_text(data)}
        form = self.form_class(data)
        if form.is_valid():
            return self.get_context_from_cleaned_data(form.cleaned_data)
        else:
            raise Exception(form.errors)

    def get_context_from_cleaned_data(self, cleaned_data):
        return unwrap_plain_text(cleaned_data["raw_json"])


class ContextFactor:
    mapping = {
        'raw': RawJSON
    }

    @classmethod
    def get_factory(cls, slug):
        return cls.mapping[slug]()


def wrap_plain_text(data):
    return {VALUE_KEY: data} if isinstance(data, str) else data


def unwrap_plain_text(data):
    return data[VALUE_KEY] if isinstance(data, dict) and VALUE_KEY in data else data
