from django import forms
from django.forms.fields import MultiValueField, CharField
from django.forms.util import flatatt
from django.forms.widgets import CheckboxInput, HiddenInput, Input, RadioSelect, RadioFieldRenderer, RadioInput, TextInput, MultiWidget
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import json

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

class BootstrapRadioInput(RadioInput):

    def __unicode__(self):
        if 'id' in self.attrs:
            label_for = ' for="%s_%s"' % (self.attrs['id'], self.index)
        else:
            label_for = ''
        choice_label = conditional_escape(force_unicode(self.choice_label))
        return mark_safe(u'<label class="radio"%s>%s %s</label>' % (label_for, self.tag(), choice_label))


class BootstrapRadioFieldRenderer(RadioFieldRenderer):

    def render(self):
        return mark_safe(u'\n'.join([u'%s'
                                      % force_unicode(w) for w in self]))

    def __iter__(self):
        for i, choice in enumerate(self.choices):
            yield BootstrapRadioInput(self.name, self.value, self.attrs.copy(), choice, i)

class BootstrapRadioSelect(RadioSelect):
    renderer = BootstrapRadioFieldRenderer


class BootstrapAddressField(MultiValueField):
    """
        The original for this was found here:
        http://stackoverflow.com/questions/7437108/saving-a-form-model-with-using-multiwidget-and-a-multivaluefield
    """
    def __init__(self,num_lines=3,*args,**kwargs):
        fields = tuple([CharField(widget=TextInput(attrs={'class':'input-xxlarge'})) for _ in range(0, num_lines)])
        self.widget = BootstrapAddressFieldWidget(widgets=[field.widget for field in fields])
        super(BootstrapAddressField,self).__init__(fields=fields,*args,**kwargs)

    def compress(self, data_list):
        return data_list


class BootstrapAddressFieldWidget(MultiWidget):

    def decompress(self, value):
        return ['']*len(self.widgets)

    def format_output(self, rendered_widgets):
        lines = list()
        for field in rendered_widgets:
            lines.append("<p>%s</p>" % field)
        return u'\n'.join(lines)
#    def value_from_datadict(self, data, files, name):
#        line_list = [widget.value_from_datadict(data,files,name+'_%s' %i) for i,widget in enumerate(self.widgets)]
#        try:
#            return line_list[0] + ' ' + line_list[1] + ' ' + line_list[2]
#        except Exception:
#            return ''

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

class BootstrapPhoneNumberInput(Input):
    input_type = 'text'

    def render(self, name, value, attrs=None):
        return mark_safe(u"""<div class="input-prepend">
        <span class="add-on">+</span>%s
        </div>""" % super(BootstrapPhoneNumberInput, self).render(name, value, attrs))



class AutocompleteTextarea(forms.Textarea):
    """
    Textarea with auto-complete.  Requires Twitter Bootstrap typeahead JS
    plugin to be available.
    
    """

    class Media:
        js = ('hqstyle/js/jquery.multi_typeahead.js',)

    def render(self, name, value, attrs=None):
        if hasattr(self, 'choices') and self.choices:
            output = mark_safe("""
<script>
$(function() {
    $("#%s").multiTypeahead({
        source: %s
    });
});
</script>\n""" % (attrs['id'], json.dumps(self.choices)))

        else:
            output = mark_safe("")

        output += super(AutocompleteTextarea, self).render(name, value,
                                                           attrs=attrs)
        return output
