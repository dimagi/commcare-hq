import collections
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.models import get_apps_in_domain


ApplicationDataSource = collections.namedtuple('ApplicationDataSource', ['application', 'source_type', 'source'])


class ApplicationDataSourceWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [forms.Select(), forms.Select(), forms.Select()]
        super(ApplicationDataSourceWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.app_id, value.source_type, value.source]
        return [''] * 3


class ApplicationDataSourceField(forms.MultiValueField):
    """
    A field that can be used in forms that allows you to select a data source from an application.
    Data sources can be forms and cases.
    """
    widget = ApplicationDataSourceWidget

    def __init__(self, enable_cases=True, enable_forms=True, *args, **kwargs):
        assert enable_cases or enable_forms, 'You must use at least cases or forms to use this field!'
        self.all_sources = {}
        self.enable_cases = enable_cases
        self.enable_forms = enable_forms
        source_choices = []
        if enable_cases:
            source_choices.append(("case", _("Case")))
        if enable_forms:
            source_choices.append(("form", _("Form")))
        application = forms.ChoiceField()
        source_type = forms.ChoiceField(choices=source_choices)
        source = forms.ChoiceField()
        super(ApplicationDataSourceField, self).__init__(fields=(application, source_type, source),
                                                         *args, **kwargs)

    def compress(self, data_list):
        return ApplicationDataSource(*data_list)

    def bootstrap(self, domain):
        self.all_sources = get_app_sources(domain)
        app_field, source_type_field, source_field = self.fields
        app_field.choices = [
            (app_id, source['name']) for app_id, source in self.all_sources.items()
        ]
        source_field.choices = []
        if self.enable_cases:
            source_field.choices.extend(
                [(ct['value'], ct['text']) for app in self.all_sources.values() for ct in app['case']]
            )
        if self.enable_forms:
            source_field.choices.extend(
                [(ct['value'], ct['text']) for app in self.all_sources.values() for ct in app['form']]
            )

        # it's super weird/annoying that you have to manually sync these
        for i, widget in enumerate(self.widget.widgets):
            widget.choices = self.fields[i].choices

        # NOTE: The corresponding knockout view model is defined in:
        #       templates/userreports/create_new_report_builder.html
        app_widget, source_type_widget, source_widget = self.widget.widgets
        app_widget.attrs = {'data-bind': 'value: application'}
        source_type_widget.attrs = {'data-bind': 'value: sourceType'}
        source_widget.attrs = {'data-bind': '''
            options: sourcesMap[application()][sourceType()],
            optionsText: function(item){return item.text},
            optionsValue: function(item){return item.value}
        '''}


def get_app_sources(domain):
    apps = get_apps_in_domain(domain, full=True, include_remote=False)
    return {
        app._id: {
            "name": app.name,
            "case": [{"text": t, "value": t} for t in app.get_case_types()],
            "form": [
                {
                    "text": form.default_name(),
                    "value": form.get_unique_id()
                } for form in app.get_forms()
            ]
        }
        for app in apps
    }
