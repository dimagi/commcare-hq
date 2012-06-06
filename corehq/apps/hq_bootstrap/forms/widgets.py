from django.forms.util import flatatt
from django.forms.widgets import CheckboxInput, HiddenInput, Input
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe

class BootstrapCheckboxInput(CheckboxInput):

    def __init__(self, attrs=None, check_test=bool, inline_label=""):
        super(BootstrapCheckboxInput, self).__init__(attrs, check_test)
        self.inline_label = inline_label

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs, type='checkbox', name=name)
        try:
            result = self.check_test(value)
        except: # Silently catch exceptions
            result = False
        if result:
            final_attrs['checked'] = 'checked'
        if value not in ('', True, False, None):
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_unicode(value)
        return mark_safe(u'<label class="checkbox"><input%s /> %s</label>' %
                         (flatatt(final_attrs), self.inline_label))

class BootstrapDisabledInput(Input):
    input_type = 'hidden'

    def render(self, name, value, attrs=None):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, type=self.input_type, name=name)
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_unicode(self._format_value(value))
        return mark_safe(u'<span class="uneditable-input %s">%s</span><input%s />' %
                         (attrs.get('class', ''), value, flatatt(final_attrs)))