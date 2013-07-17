import pytz
from django.template.loader import render_to_string
#from corehq.apps.reports.cache import CacheableRequestMixIn, request_cache
from corehq.apps.reports.cache import CacheableRequestMixIn
from dimagi.utils.decorators.memoized import memoized
# For translations
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


class BaseReportFilter(CacheableRequestMixIn):   # (CacheableRequestMixIn):
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
    help_text = None

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
            'help_text': self.help_text,
        })
        filter_context = self.filter_context
        if not (filter_context, dict):
            raise ValueError("filter_context must return a dict.")
        self.context.update(filter_context)
        return render_to_string(self.template, self.context)

    @classmethod
    def get_value(cls, request, domain):
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
        return self.get_value(self.request, self.domain) or ""

    @property
    def filter_context(self):
        options = self.options
        if not isinstance(options, list) and not isinstance(options[0], tuple) and not len(options[0]) == 2:
            raise ValueError("options must return a list of option tuples [('value','text')].")
        options = [dict(val=o[0], text=o[1]) for o in self.options]
        return {
            'select': {
                'options': options,
                'default_text': self.default_text,
                'selected': self.selected,
            }
        }

    @classmethod
    def get_value(cls, request, domain):
        value = super(BaseSingleOptionFilter, cls).get_value(request, domain)
        if isinstance(cls, cls):
            instance = cls
        else:
            instance = cls(request, domain)
        valid_options = [op[0] for op in instance.options]
        if value in valid_options:
            return value
        return None


class BaseMutipleOptionFilter(BaseSingleOptionFilter):
    """
        Displays a multiselect field.
    """
    template = "reports/filters/multi_option.html"
    default_options = [] # specify a list

    @classmethod
    def get_value(cls, request, domain):
        return request.GET.getlist(cls.slug)

    @property
    @memoized
    def selected(self):
        return self.get_value(self.request, self.domain) or self.default_options


class BaseMultipleOptionTypeaheadFilter(BaseMutipleOptionFilter):
    """
        Displays a select2 field
    """
    template = "reports/filters/select2_option.html"


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

        use_only_last => Whether to indicate to the user that they must move all the way through the hierarchy
            and select a final option before the result is usable. For example, you can't just pick an application
            and show all of its forms, you must select exactly one form.
    """
    template = "reports/filters/drilldown_options.html"
    use_only_last = False
    drilldown_empty_text = ugettext_noop("No Data Available")
    is_cacheable = True

    @property
    def drilldown_map(self):
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
        raise NotImplementedError("drilldown_map must be implemented")
    
    @classmethod
    def get_labels(cls):
        """
            Returns a list of ('label', default text/caption', 'slug') tuples.
            ex: [
                ('Application', 'Select Application...', 'app'),
                ('Module', 'Select Module...', 'module'),
                ('Form', 'Select Form...', 'form')
            ]
        """
        raise NotImplementedError("get_labels must be implemented")

    @property
    def selected(self):
        selected = []
        for label in self.rendered_labels:
            value = self._get_label_value(self.request, label)
            if not value['value']:
                break
            selected.append(value['value'])
        return selected

    @property
    def rendered_labels(self):
        """
            Modify the default set of labels here.
        """
        return self.get_labels()

    @property
#    @request_cache('drilldownfiltercontext')
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            controls.append({
                'label': label[0],
                'default_text': label[1],
                'slug': label[2],
                'level': level,
            })

        drilldown_map = list(self.drilldown_map)
        return {
            'option_map': drilldown_map,
            'controls': controls,
            'selected': self.selected,
            'use_last': self.use_only_last,
            'notifications': self.final_notifications,
            'empty_text': self.drilldown_empty_text,
            'is_empty': not drilldown_map,
        }

    @property
    def final_notifications(self):
        """
            Not required, but this can be used to display a message when the drill down is complete
            that's based on the value of the final drill down option.
            ex: {'xmlns_of_form': 'This form does not have a unique id.'}
        """
        return {}


    @property
    @memoized
    def GET_values(self):
        values = []
        for label in self.rendered_labels:
            value = self._get_label_value(self.request, label)
            if not value['value']:
                break
            values.append(value)
        return values

    def _map_structure(self, val, text, next=None):
        if next is None:
            next = []
        return {
            'val': val,
            'text': text,
            'next': next,
            }


    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[2])
        val = request.GET.get('%s_%s' % (cls.slug, str(label[2])))
        return {
            'slug': slug,
            'value': val,
        }

    @classmethod
    def get_value(cls, request, domain):
        instance = cls(request, domain)
        return instance.GET_values, instance


