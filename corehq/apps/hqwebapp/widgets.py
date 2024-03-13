import collections
import json

from django import forms
from django.forms.utils import flatatt
from django.forms.widgets import CheckboxInput, Input
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.html import format_html, conditional_escape
from django.utils.translation import gettext_noop

from corehq.util.json import CommCareJSONEncoder

from dimagi.utils.dates import DateSpan

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import html_attr


class BootstrapCheckboxInput(CheckboxInput):
    template_name = "hqwebapp/crispy/checkbox_widget.html"

    def __init__(self, attrs=None, check_test=bool, inline_label=""):
        super().__init__(attrs, check_test)
        self.inline_label = inline_label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        extra_attrs = {'type': 'checkbox', 'name': conditional_escape(name)}
        extra_attrs.update(self.attrs)
        final_attrs = self.build_attrs(attrs, extra_attrs=extra_attrs)
        try:
            result = self.check_test(value)
        except Exception:  # Silently catch exceptions
            result = False
        if result:
            final_attrs['checked'] = 'checked'
        if value not in ('', True, False, None):
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_str(value)
        from corehq.apps.hqwebapp.utils.bootstrap import get_bootstrap_version, BOOTSTRAP_5
        use_bootstrap5 = get_bootstrap_version() == BOOTSTRAP_5
        final_attrs['class'] = 'form-check-input' if use_bootstrap5 else 'bootstrapcheckboxinput'
        context.update({
            'use_bootstrap5': use_bootstrap5,
            'input_id': final_attrs.get('id'),
            'inline_label': self.inline_label,
            'attrs': mark_safe(flatatt(final_attrs)),  # nosec: trusting the user to sanitize attributes
        })
        return context


class BootstrapSwitchInput(BootstrapCheckboxInput):
    """Only valid for forms using Bootstrap5"""
    template_name = "hqwebapp/crispy/switch_widget.html"


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
        if isinstance(val, collections.Sequence) and not isinstance(val, (str, str)):
            # if its a tuple or list
            return {"id": val[0], "text": val[1]}
        elif val is None:
            return None
        else:
            # if its a scalar
            return {"id": val, "text": val}


class Select2Ajax(_Select2AjaxMixin, forms.Select):
    def __init__(self, attrs=None, page_size=20, multiple=False):
        self.page_size = page_size
        self.multiple = multiple
        self._initial = None
        super(Select2Ajax, self).__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs.update({
            'class': 'form-control hqwebapp-select2-ajax',
            'data-initial': json.dumps(self._initial if self._initial is not None else self._clean_initial(value)),
            'data-endpoint': self.url,
            'data-page-size': self.page_size,
            'data-multiple': '1' if self.multiple else '0',
        })
        return super(Select2Ajax, self).render(name, value, attrs, renderer=renderer)


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
        Range.LAST_7: gettext_noop('Last 7 Days'),
        Range.LAST_MONTH: gettext_noop('Last Month'),
        Range.LAST_30_DAYS: gettext_noop('Last 30 Days'),
    }
    separator = gettext_noop(' to ')

    def __init__(self, attrs=None, default_datespan=None):
        self.default_datespan = default_datespan
        super(DateRangePickerWidget, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None, renderer=None):
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

        output = super(DateRangePickerWidget, self).render(name, value, attrs, renderer)
        return format_html(
            '<div class="input-group hqwebapp-datespan">'
            '   <span class="input-group-addon"><i class="fa-solid fa-calendar-days"></i></span>'
            '   {}'
            '</div>',
            output
        )


class SelectToggle(forms.Select):

    def __init__(self, choices=None, attrs=None, apply_bindings=False):
        self.apply_bindings = apply_bindings
        self.params = {}
        attrs = attrs or {}
        self.params['value'] = attrs.get('ko_value', '')
        super(SelectToggle, self).__init__(choices=choices, attrs=attrs)
        self.attrs['disabled'] = attrs.get('disabled', 'false')

    def render(self, name, value, attrs=None, renderer=None):
        return '''
            <select-toggle data-apply-bindings="{apply_bindings}"
                            params="name: '{name}',
                                    id: '{id}',
                                    value: {value},
                                    disabled: {disabled},
                                    options: {options}"></select-toggle>
        '''.format(
            apply_bindings="true" if self.apply_bindings else "false",
            name=name,
            id=html_attr(attrs.get('id', '')),
            value=html_attr(self.params['value'] or '"{}"'.format(html_attr(value))),
            disabled=html_attr(self.attrs['disabled']),
            options=html_attr(json.dumps(
                [{'id': c[0], 'text': c[1]} for c in self.choices],
                cls=CommCareJSONEncoder
            ))
        )


class GeoCoderInput(Input):

    def __init__(self, attrs=None):
        super(GeoCoderInput, self).__init__(attrs=attrs)

    def render(self, name, value, attrs=None, renderer=None):
        self.input_type = 'hidden'
        if isinstance(value, dict):
            value = json.dumps(value)
        output = super(GeoCoderInput, self).render(name, value, attrs, renderer)
        return format_html('<div class="geocoder-proximity">{}</div>', output)
