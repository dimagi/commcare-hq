import pytz
from django.template.loader import render_to_string
from dimagi.utils.decorators.memoized import memoized
# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

class BaseReportFilter(object):
    """
        For filtering the results of CommCare HQ Reports.

        slug => the parameter you get back from the request
        template => the template to render this filter
        label => the filter's label
    """
    slug = None
    template = None
    label = None
    css_class = "span4"

    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None):
        if self.slug is None:
            raise NotImplementedError("slug is required")
        if self.template is None:
            raise NotImplementedError("a template must be specified")
        if self.label is None:
            raise NotImplementedError("label is required")
        self.request = request
        self.domain = domain
        self.timezone = timezone
        self.parent_report = parent_report
        self.context = {}

    @property
    def is_disabled(self):
        """
            If necessary, determine whether to show this filter based on the results of surrounding (related) filters.
        """
        return False

    @property
    def filter_context(self):
        """
            Context for rendering the filter.
            Should return a dict.
        """
        raise NotImplementedError("filter_context must be overridden")

    def render(self):
        if self.is_disabled:
            return ""
        self.context.update({
            'slug': self.slug,
            'label': self.label,
            'css_id': 'report_filter_%s' % self.slug,
            'css_class': self.css_class,
        })
        filter_context = self.filter_context
        if not (filter_context, dict):
            raise ValueError("filter_context must return a dict.")
        self.context.update(filter_context)
        return render_to_string(self.template, self.context)

    @classmethod
    def get_value(cls, request):
        return request.GET.get(cls.slug)


class BaseSingleOptionFilter(BaseReportFilter):
    """
        Displays a select field.
    """
    template = "reports/filters/single_option.html"
    default_text = ugettext_noop("Filter by...")

    @property
    def options(self):
        """
            Options should return a list of tuples formatted like:
            [('value', 'display_text')]
        """
        raise NotImplementedError("options must be overridden")

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request) or ""

    @property
    def filter_context(self):
        options = self.options
        if not isinstance(options, list) and not isinstance(options[0], tuple) and not len(options[0]) == 2:
            raise ValueError("options must return a list of option tuples [('value','text')].")
        options = [dict(val=o[0], text=o[1]) for o in options]
        return {
            'select': {
                'options': options,
                'default_text': self.default_text,
                'selected': self.selected,
            }
        }


class BaseSingleOptionTypeaheadFilter(BaseSingleOptionFilter):
    """
        Displays a combobox (select field with typeahead).
    """
    template = "reports/filters/single_option_typeahead.html"


class BaseDrilldownOptionFilter(BaseReportFilter):
    """
        Displays multiple select fields that display in a hierarchial order and drill down to one value.
        Ex:
        Select Application: <applications>
        ---> Select Module: <module options based on selected application (if selected)>
        ---------> Select Form: <form_options based on selected module (if selected)>

        use_only_last => Whether to indicate to the user that they must move all the way through the hierarchy before
            the result is usable. (eg: you can't just pick an application and show all of its forms,
            you must select exactly one form)
    """
    template = "reports/filters/drilldown_options.html"
    use_only_last = False

    @property
    def option_map(self):
        """
            Should return a structure like:
            [{
                'val': <value>,
                'text': <text>,
                'next': [
                        {
                            'val': <value>,
                            'text' <text>,
                            'next': [...]
                        },
                        {...}
                    ]
            },
            {...}
            ]
        """
        raise NotImplementedError("options must be implemented")

    @property
    def selected(self):
        selected = []
        for label in self.labels():
            value = self._get_label_value(self.request, label)
            if not value:
                break
            selected.append(value)
        return selected

    @property
    def filter_context(self):
        selects = []
        for level, label in enumerate(self.labels()):
            selects.append({
                'label': label[0],
                'default_text': label[1],
                'slug': label[2],
                'level': level,
            })
        return {
            'option_map': self.option_map,
            'selects': selects,
            'selected': self.selected,
            'use_last': self.use_only_last,
        }

    @classmethod
    def labels(cls):
        """
            Returns a list of ('label', default text/caption', 'slug') tuples.
            ex: [
                ('Application', 'Select Application...', 'app'),
                ('Module', 'Select Module...', 'module'),
                ('Form', 'Select Form...', 'form')
                ]
        """
        raise NotImplementedError("label_hierarchy must be implemented")

    @classmethod
    def _get_label_value(cls, request, label):
        return request.GET.get('%s_%s' % (cls.slug, str(label[2])))

    @classmethod
    def get_value(cls, request):
        values = {}
        for label in cls.labels():
            value = cls._get_label_value(request, label)
            if not value:
                break
            values[str(label[2])] = value
        return values


