from __future__ import absolute_import
from __future__ import unicode_literals
import collections
from django import forms
from django.forms.fields import MultiValueField, CharField
from django.forms.utils import flatatt
from django.forms.widgets import (
    CheckboxInput,
    Input,
    TextInput,
    MultiWidget,
)
from django.template.loader import render_to_string
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
import json
from django.utils.translation import ugettext_noop
from dimagi.utils.dates import DateSpan
import six
from six.moves import range


class BootstrapCheckboxInput(CheckboxInput):

    def __init__(self, attrs=None, check_test=bool, inline_label=""):
        super(BootstrapCheckboxInput, self).__init__(attrs, check_test)
        self.inline_label = inline_label

    def render(self, name, value, attrs=None):
        extra_attrs = {'type': 'checkbox', 'name': name}
        extra_attrs.update(self.attrs)
        final_attrs = self.build_attrs(attrs, extra_attrs=extra_attrs)
        try:
            result = self.check_test(value)
        except: # Silently catch exceptions
            result = False
        if result:
            final_attrs['checked'] = 'checked'
        if value not in ('', True, False, None):
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_text(value)
        return mark_safe('<label class="checkbox"><input%s /> %s</label>' %
                         (flatatt(final_attrs), self.inline_label))


class AutocompleteTextarea(forms.Textarea):
    """
    Textarea with auto-complete.  Uses a custom extension on top of Twitter
    Bootstrap's typeahead plugin.
    """

    def render(self, name, value, attrs=None):
        if hasattr(self, 'choices') and self.choices:
            if not attrs:
                attrs = {}
            attrs.update({
                'class': 'hqwebapp-autocomplete form-control',
                'data-choices': json.dumps([{'text': c, 'id': c} for c in self.choices]),
            })

        return super(AutocompleteTextarea, self).render(name, value, attrs=attrs)


class _Select2Mixin(object):

    class Media(object):
        css = {
            'all': ('select2-3.4.5-legacy/select2.css',)
        }
        js = ('select2-3.4.5-legacy/select2.js',)

    def render(self, name, value, attrs=None, choices=()):
        output = super(_Select2Mixin, self).render(name, value, attrs)
        output += """
            <script>
                $(function() {
                    $('#%s').select2({ width: 'resolve' });
                });
            </script>
        """ % attrs.get('id')
        return mark_safe(output)


class Select2(_Select2Mixin, forms.Select):
    pass


class Select2MultipleChoiceWidget(_Select2Mixin, forms.SelectMultiple):
    pass


class Select2Ajax(forms.TextInput):
    """
    A Select2 widget that loads its options asynchronously.

    You must use `set_url()` to set the url. This will usually be done in the form's __init__() method.
    The url is not specified in the form class definition because in most cases the url will be dependent on the
    domain of the request.
    """
    def __init__(self, attrs=None, page_size=20, multiple=False):
        self.page_size = page_size
        self.multiple = multiple
        self._initial = None
        super(Select2Ajax, self).__init__(attrs)

    def set_url(self, url):
        self.url = url

    def set_initial(self, val):
        self._initial = val

    def _clean_initial(self, val):
        if isinstance(val, collections.Sequence) and not isinstance(val, (str, six.text_type)):
            # if its a tuple or list
            return {"id": val[0], "text": val[1]}
        elif val is None:
            return None
        else:
            # if its a scalar
            return {"id": val, "text": val}

    def render(self, name, value, attrs=None):
        attrs.update({
            'class': 'form-control hqwebapp-select2-ajax',
            'data-initial': json.dumps(self._initial if self._initial is not None else self._clean_initial(value)),
            'data-endpoint': self.url,
            'data-page-size': self.page_size,
            'data-multiple': '1' if self.multiple else '0',
        })
        output = super(Select2Ajax, self).render(name, value, attrs)
        return mark_safe(output)


class DateRangePickerWidget(Input):
    """
    Extends the standard input widget to render a Date Range Picker Widget.
    Documentation and Demo here: http://www.daterangepicker.com/

    usage:
    apply the following decorator to your view's dispatch method

    @use_daterangepicker
    def dispatch(self, request, *args, **kwargs):
        super(self, MyView).dispatch(request, *args, **kwargs)
    """

    class Range(object):
        LAST_7 = 'last_7_days'
        LAST_MONTH = 'last_month'
        LAST_30_DAYS = 'last_30_days'

    range_labels = {
        Range.LAST_7: ugettext_noop('Last 7 Days'),
        Range.LAST_MONTH: ugettext_noop('Last Month'),
        Range.LAST_30_DAYS: ugettext_noop('Last 30 Days'),
    }
    separator = ugettext_noop(' to ')

    def __init__(self, attrs=None, range_labels=None, separator=None,
                 default_datespan=None):
        self.range_labels = range_labels or self.range_labels
        self.separator = separator or self.separator
        self.default_datespan = default_datespan
        super(DateRangePickerWidget, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs)
        output = super(DateRangePickerWidget, self).render(name, value, attrs)
        # yes, I know inline html in python is gross, but this is what the
        # built in django widgets are doing. :|
        output += """
            <script>
                $(function () {
                    var separator = '%(separator)s';
                    var report_labels = JSON.parse('%(range_labels_json)s');
                    $('#%(elem_id)s').createDateRangePicker(
                        report_labels, separator, '%(startdate)s',
                        '%(enddate)s'
                    );
                });
            </script>
        """ % {
            'elem_id': final_attrs.get('id'),
            'separator': self.separator,
            'range_labels_json': json.dumps(self.range_labels),
            'startdate': (self.default_datespan.startdate.strftime('%m/%d/%Y')
                          if (isinstance(self.default_datespan, DateSpan)
                              and self.default_datespan.startdate is not None)
                          else ''),
            'enddate': (self.default_datespan.enddate.strftime('%m/%d/%Y')
                        if (isinstance(self.default_datespan, DateSpan)
                            and self.default_datespan.enddate is not None)
                        else ''),
        }
        output = """
            <span class="input-group-addon"><i class="fa fa-calendar"></i></span>
        """ + output
        output = '<div class="input-group">{}</div>'.format(output)
        return mark_safe(output)
