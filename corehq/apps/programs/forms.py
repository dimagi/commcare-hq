from django import forms
from django.utils.translation import gettext as _

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.programs.models import Program


class ProgramForm(forms.Form):
    name = forms.CharField(max_length=100)

    def __init__(self, program, *args, **kwargs):
        self.program = program

        kwargs['initial'] = self.program._doc
        super(ProgramForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'form-label'

        # don't let users rename the uncategorized
        # program
        if program.default:
            self.fields['name'].required = False
            self.fields['name'].widget.attrs['readonly'] = True

        self.helper.layout = crispy.Layout('name')

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError(_('This field is required.'))

        other_program_names = [
            p.name for p in Program.by_domain(self.program.domain)
            if p.get_id != self.program._id
        ]
        if name in other_program_names:
            raise forms.ValidationError(_('Name already in use'))

        return name

    def save(self, instance=None, commit=True):
        if self.errors:
            raise ValueError(_('Form does not validate'))

        program = instance or self.program

        setattr(program, 'name', self.cleaned_data['name'])

        if commit:
            program.save()

        return program
