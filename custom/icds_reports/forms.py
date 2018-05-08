from __future__ import absolute_import
from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_noop
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.hqwebapp import crispy as hqcrispy
from django.utils.translation import ugettext_lazy as _

from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain


class AppTranslationsForm(forms.Form):
    app_id = forms.ChoiceField(label=ugettext_noop("App"), choices=(), required=True)
    version = forms.IntegerField(label=ugettext_noop("Build Number"), required=True)
    source_lang = forms.ChoiceField(label=ugettext_noop("Source Language"),
                                    choices=[('en', 'English')])
    target_lang = forms.ChoiceField(label=ugettext_noop("Source Language"),
                                    choices=[('hin', 'Hindi'), ('mr', 'Marathi'),
                                             ('te', 'telugu')])

    def __init__(self, domain, *args, **kwargs):
        super(AppTranslationsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        self.fields['app_id'].choices = tuple((app.id, app.name) for app in get_brief_apps_in_domain(domain))

        self.helper.layout = Layout(
            'app_id',
            'version',
            'source_lang',
            'target_lang',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Submit Translation To Transifex"),
                    type="submit",
                    css_class="btn btn-primary btn-lg disable-on-submit",
                )
            )
        )
