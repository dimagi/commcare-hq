"""
DO NOT WRITE ANY NEW FUNCTIONALITY BASED ON THIS FILE
This is being kept around only to support legacy reports
"""
import warnings

from django.template.loader import render_to_string

import pytz

from corehq.apps.hqwebapp.crispy import CSS_FIELD_CLASS, CSS_LABEL_CLASS


class ReportField(object):
    slug = ""
    template = ""
    is_cacheable = False

    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None,
                 css_label=None, css_field=None):
        warnings.warn(
            "ReportField (%s) is deprecated." % (
                self.__class__.__name__
            ),
            DeprecationWarning,
        )
        self.context = {}
        self.request = request
        self.domain = domain
        self.timezone = timezone
        self.parent_report = parent_report
        self.css_label = css_label or (CSS_LABEL_CLASS + ' control-label')
        self.css_field = css_field or CSS_FIELD_CLASS

    def render(self):
        if not self.template: return ""
        self.context["slug"] = self.slug
        self.context['css_label_class'] = self.css_label
        self.context['css_field_class'] = self.css_field
        self.update_context()
        return render_to_string(self.template, self.context)

    def update_context(self):
        """
        If your select field needs some context (for example, to set the default) you can set that up here.
        """
        pass


class BooleanField(ReportField):
    slug = "checkbox"
    label = "hello"
    template = "reports/partials/checkbox.html"

    def update_context(self):
        self.context['label'] = self.label
        self.context[self.slug] = self.request.GET.get(self.slug, False)
        self.context['checked'] = self.request.GET.get(self.slug, False)
