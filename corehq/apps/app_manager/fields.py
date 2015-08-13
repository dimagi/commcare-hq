from django.utils.datastructures import SortedDict
import collections
from django import forms
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain


ApplicationDataSource = collections.namedtuple('ApplicationDataSource', ['application', 'source_type', 'source'])


class ApplicationDataSourceUIHelper(object):
    """
    A helper object that can be used in forms that allows you to select a data source from an application.
    Data sources can be forms and cases.

    To use it you must do the following:

    - Add this helper as a member variable of your form
    - Call helper.boostrap() with the domain.
    - Add helper.get_fields() to the form fields.
    - Add the following knockout bindings to your template:

        $(function () {
            ko.applyBindings({
                application: ko.observable(""),
                sourceType: ko.observable(""),
                sourcesMap: {{ sources_map|JSON }}
            }, $("#FORM").get(0));
        });

    Where FORM is a selector for your form and sources_map is the .all_sources property from this object
    (which gets set after bootstrap).

    See usages for examples.
    """

    def __init__(self, enable_cases=True, enable_forms=True):
        self.all_sources = {}
        self.enable_cases = enable_cases
        self.enable_forms = enable_forms
        source_choices = []
        if enable_cases:
            source_choices.append(("case", _("Case")))
        if enable_forms:
            source_choices.append(("form", _("Form")))

        self.application_field = forms.ChoiceField(label=_('Application'), widget=forms.Select())
        if enable_cases and enable_forms:
            self.source_type_field = forms.ChoiceField(label=_('Type of Data'),
                                                       choices=source_choices,
                                                       widget=forms.Select(choices=source_choices))
        else:
            self.source_type_field = forms.ChoiceField(choices=source_choices,
                                                       widget=forms.HiddenInput(),
                                                       initial=source_choices[0][0])

        self.source_field = forms.ChoiceField(label=_('Data Source'), widget=forms.Select())

    def bootstrap(self, domain):
        self.all_sources = get_app_sources(domain)
        self.application_field.choices = [
            (app_id, source['name']) for app_id, source in self.all_sources.items()
        ]
        self.source_field.choices = []

        def _add_choices(field, choices):
            field.choices.extend(choices)
            # it's weird/annoying that you have to manually sync these
            field.widget.choices.extend(choices)

        if self.enable_cases:
            _add_choices(
                self.source_field,
                [(ct['value'], ct['text']) for app in self.all_sources.values() for ct in app['case']]
            )
        if self.enable_forms:
            _add_choices(
                self.source_field,
                [(ct['value'], ct['text']) for app in self.all_sources.values() for ct in app['form']]
            )

        # NOTE: This corresponds to a view-model that must be initialized in your template.
        # See the doc string of this class for more information.
        self.application_field.widget.attrs = {'data-bind': 'value: application'}
        self.source_type_field.widget.attrs = {'data-bind': 'value: sourceType'}
        self.source_field.widget.attrs = {'data-bind': '''
            options: sourcesMap[application()][sourceType()],
            optionsText: function(item){return item.text},
            optionsValue: function(item){return item.value}
        '''}

    def get_fields(self):
        fields = collections.OrderedDict()
        fields['source_type'] = self.source_type_field
        fields['application'] = self.application_field
        fields['source'] = self.source_field
        return fields

    def get_app_source(self, data_dict):
        return ApplicationDataSource(data_dict['application'], data_dict['source_type'], data_dict['source'])


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
