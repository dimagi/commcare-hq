from django import forms
from django.utils.translation import ugettext_noop, ugettext as _
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from corehq.apps.style import crispy as hqcrispy

OFFICES = [
    'INC', 'DSI', 'DSA', 'DWA',
]
COLORS = [
    'red', 'orange', 'yellow', 'green', 'blue', 'indigo', 'violet'
]


class SelectControlDemoForm(forms.Form):
    """This form demonstrates the use of different types of selects.
    """
    office = forms.ChoiceField(
        label=ugettext_noop("Dimagi Office (Single Select)"),
        required=False,
        # only do this if the choices are static:
        choices=[(o, o) for o in OFFICES]
    )
    colors = forms.MultipleChoiceField(
        label=ugettext_noop("Favorite Colors (Multi Select)"),
        required=False,
        # only do this if the choices are static:
        choices=[(c, c) for c in COLORS]
    )
    language = forms.ChoiceField(
        label=ugettext_noop("Language (Select2 Single)"),
        required=False,
    )
    genres = forms.MultipleChoiceField(
        label=ugettext_noop("Music Genre (Select2 Multi)"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(SelectControlDemoForm, self).__init__(*args, **kwargs)
        # note that we apply choices to a field AFTER the call to super
        self.fields['language'].choices = _language_resource()
        self.fields['genres'].choices = _genre_resource()

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Standard Selects"),
                'office',
                'colors',
                'language',
                'genres',
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(_("Update Selects"),
                                        type='submit',
                                        css_class='btn-primary'),
                offsets='col-sm-offset-3 col-md-offset-2 col-lg-offset-2',
            ),
        )


def _language_resource():
    """Just for demoing purposes. Populating a ChoiceField would likely come
    from a DB or other resource.
    """
    return [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('ot', 'Other'),
    ]


def _genre_resource():
    GENRES = [
        'pop', 'rock', 'rap', 'r&b', 'blues', 'house', 'techno', 'minimal',
        'trap', 'drum & bass', 'acid', 'edm', 'bass', 'happy hardcore',
        'electronic', 'orchestral', 'choral', 'musique concrete'
    ]
    return [(g, g) for g in GENRES]
