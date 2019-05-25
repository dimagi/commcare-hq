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
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import html_attr


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


class _Select2AjaxMixin():
    """
    A Select2 widget that loads its options asynchronously.

    You must use `set_url()` to set the url. This will usually be done in the form's __init__() method.
    The url is not specified in the form class definition because in most cases the url will be dependent on the
    domain of the request.
    """
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


class Select2AjaxV4(_Select2AjaxMixin, forms.Select):
    def __init__(self, attrs=None, page_size=20, multiple=False):
        self.page_size = page_size
        self.multiple = multiple
        self._initial = None
        super(Select2AjaxV4, self).__init__(attrs)

    def render(self, name, value, attrs=None):
        attrs.update({
            'class': 'form-control hqwebapp-select2-ajax-v4',
            'data-initial': json.dumps(self._initial if self._initial is not None else self._clean_initial(value)),
            'data-endpoint': self.url,
            'data-page-size': self.page_size,
            'data-multiple': '1' if self.multiple else '0',
        })
        output = super(Select2AjaxV4, self).render(name, value, attrs)
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

    def __init__(self, attrs=None, default_datespan=None):
        self.default_datespan = default_datespan
        super(DateRangePickerWidget, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None):
        startdate = ''
        enddate = ''
        if isinstance(self.default_datespan, DateSpan):
            if self.default_datespan.startdate is not None:
                startdate = self.default_datespan.startdate.strftime('%m/%d/%Y')
            if self.default_datespan.enddate is not None:
                enddate = self.default_datespan.enddate.strftime('%m/%d/%Y')

        attrs.update({
            'data-separator': self.separator,
            'data-labels': json.dumps(self.range_labels),
            'data-start-date': startdate,
            'data-end-date': enddate,
        })
        final_attrs = self.build_attrs(attrs)

        output = super(DateRangePickerWidget, self).render(name, value, attrs)
        return mark_safe("""
            <div class="input-group hqwebapp-datespan">
                <span class="input-group-addon"><i class="fa fa-calendar"></i></span>
                {}
            </div>
        """.format(output))


class SelectToggle(forms.Select):

    def __init__(self, choices=None, attrs=None, apply_bindings=False):
        self.apply_bindings = apply_bindings
        self.params = {}
        attrs = attrs or {}
        self.params['value'] = attrs.get('ko_value', '')
        super(SelectToggle, self).__init__(choices=choices, attrs=attrs)

    def render(self, name, value, attrs=None):
        return '''
            <select-toggle data-apply-bindings="{apply_bindings}"
                           params="name: '{name}',
                                   id: '{id}',
                                   value: {value},
                                   options: {options}"></select-toggle>
        '''.format(apply_bindings="true" if self.apply_bindings else "false",
                   name=name,
                   id=html_attr(attrs.get('id', '')),
                   value=html_attr(self.params['value'] or '"{}"'.format(html_attr(value))),
                   options=html_attr(json.dumps([{'id': c[0], 'text': c[1]} for c in self.choices])))
