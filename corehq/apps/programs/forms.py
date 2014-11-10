from django import forms
from corehq.apps.programs.models import Program
from django.utils.translation import ugettext as _


class ProgramForm(forms.Form):
    name = forms.CharField(max_length=100)

    def __init__(self, program, *args, **kwargs):
        self.program = program

        kwargs['initial'] = self.program._doc
        super(ProgramForm, self).__init__(*args, **kwargs)

        # don't let users rename the uncategorized
        # program
        if program.default:
            self.fields['name'].required = False
            self.fields['name'].widget.attrs['readonly'] = True

    def clean_name(self):
        name = self.cleaned_data['name']

        other_program_names = [
            p['name'] for p in Program.by_domain(self.program.domain, wrap=False)
            if p['_id'] != self.program._id
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
