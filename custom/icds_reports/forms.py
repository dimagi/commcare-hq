from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy
from django.conf import settings
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy

from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.dbaccessors import get_available_versions_for_app


class AppTranslationsForm(forms.Form):
    app_id = forms.ChoiceField(label=ugettext_lazy("App"), choices=(), required=True)
    version = forms.IntegerField(label=ugettext_lazy("Build Number"), required=False,
                                 help_text=ugettext_lazy("Leave blank to use current application state"))
    transifex_project_slug = forms.ChoiceField(label=ugettext_lazy("Trasifex project"), choices=(),
                                               required=True)
    source_lang = forms.ChoiceField(label=ugettext_lazy("Source Language"),
                                    choices=[('en', ugettext_lazy('English')),
                                             ('hin', ugettext_lazy('Hindi')),
                                             ('mr', ugettext_lazy('Marathi')),
                                             ('te', ugettext_lazy('Telugu'))]
                                    )
    # Unfortunately transifex api does not provide a way to pull all possible target languages and
    # allow us to just add a checkbox instead of selecting a single/multiple target languages at once
    target_lang = forms.ChoiceField(label=ugettext_lazy("Target Language"),
                                    choices=[(None, ugettext_lazy('Select Target Language')),
                                             ('ori', ugettext_lazy('Oriya')),
                                             ('hin', ugettext_lazy('Hindi')),
                                             ('mr', ugettext_lazy('Marathi')),
                                             ('te', ugettext_lazy('Telugu'))],
                                    help_text=ugettext_lazy("Leave blank to skip")
                                    )

    def __init__(self, domain, *args, **kwargs):
        super(AppTranslationsForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        self.fields['app_id'].choices = tuple((app.id, app.name) for app in get_brief_apps_in_domain(domain))
        if settings.TRANSIFEX_DETAILS:
            self.fields['transifex_project_slug'].choices = (
                tuple((slug, slug)
                      for slug in settings.TRANSIFEX_DETAILS.get('project').get(domain))
            )
        self.helper.layout = Layout(
            'app_id',
            'version',
            'transifex_project_slug',
            'source_lang',
            'target_lang',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy("Submit files for translation to Transifex"),
                    type="submit",
                    css_class="btn btn-primary btn-lg disable-on-submit",
                )
            )
        )

    def clean_version(self):
        version = self.cleaned_data['version']
        if version:
            app_id = self.cleaned_data['app_id']
            available_versions = get_available_versions_for_app(self.domain, app_id)
            if version not in available_versions:
                raise forms.ValidationError(ugettext_lazy('Version not available for app'))
        return version
