"""
DO NOT WRITE ANY NEW FUNCTIONALITY BASED ON THIS FILE
This is being kept around only to support legacy reports
"""
from django.template.loader import render_to_string
import pytz
import warnings
from django.utils.translation import ugettext_noop
import uuid
from corehq.apps.hqwebapp.crispy import CSS_LABEL_CLASS, CSS_FIELD_CLASS


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


class ReportSelectField(ReportField):
    slug = "generic_select"
    name = ugettext_noop("Generic Select")
    template = "reports/dont_use_fields/select_generic.html"
    default_option = ugettext_noop("Select Something...")
    options = [dict(val="val", text="text")]
    cssId = "generic_select_box"
    cssClasses = "span4"
    selected = None
    hide_field = False
    as_combo = False
    placeholder = ''
    help_text = ''

    def __init__(self, *args, **kwargs):
        super(ReportSelectField, self).__init__(*args, **kwargs)
        # need to randomize cssId so knockout bindings won't clobber each other
        # when multiple select controls on screen at once
        nonce = uuid.uuid4().hex[-12:]
        self.cssId = '%s-%s' % (self.cssId, nonce)

    def update_params(self):
        self.selected = self.request.GET.get(self.slug)

    def update_context(self):
        self.update_params()
        self.context['hide_field'] = self.hide_field
        self.context['help_text'] = self.help_text
        self.context['select'] = dict(
            options=self.options,
            default=self.default_option,
            cssId=self.cssId,
            cssClasses=self.cssClasses,
            label=self.name,
            selected=self.selected,
            use_combo_box=self.as_combo,
            placeholder=self.placeholder,
        )


class BooleanField(ReportField):
    slug = "checkbox"
    label = "hello"
    template = "reports/partials/checkbox.html"

    def update_context(self):
        self.context['label'] = self.label
        self.context[self.slug] = self.request.GET.get(self.slug, False)
        self.context['checked'] = self.request.GET.get(self.slug, False)
