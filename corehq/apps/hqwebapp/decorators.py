from collections import defaultdict
from functools import wraps

from corehq.apps.hqwebapp.utils.bootstrap import set_bootstrap_version5


def use_daterangepicker(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the daterangepicker library at the base template
    level.

    Example:

    @use_daterangepicker
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """

    return set_request_flag(view_func, 'use_daterangepicker')


def use_jquery_ui(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the jquery-ui library at the base template
    level.

    Example:

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_jquery_ui')


def use_multiselect(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the multiselect library at the base template
    level.

    Example:

    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_multiselect')


def use_nvd3(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the nvd3 library at the base template
    level. nvd3 is a library of charts for d3.

    Example:

    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_nvd3')


def use_nvd3_v3(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the nvd3 library at the base template
    level. nvd3 Version 3 is a library of charts for d3.

    Example:

    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_nvd3_v3')


def use_datatables(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the datatables library at the base template
    level.

    Example:

    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_datatables')


def use_timepicker(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the timepicker library at the base template
    level.

    Example:

    @use_timepicker
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_timepicker')


def use_ko_validation(view_func):
    """Use this decorator to use knockout validation in knockout forms

    Example Tag Usage:

    @use_ko_validation
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    return set_request_flag(view_func, 'use_ko_validation')


def use_bootstrap5(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable Boostrap 5 features for the included template.

    Example:
        @use_bootstrap5
        def dispatch(self, request, *args, **kwargs):
            return super().dispatch(request, *args, **kwargs)

    Or alternatively:
        @method_decorator(use_bootstrap5, name='dispatch')
        class MyViewClass(MyViewSubclass):
            ...
    """
    return get_wrapped_view(view_func, lambda r: set_bootstrap_version5())


def use_tempusdominus(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to include CSS for Tempus Dominus (Date and/or Time picking widget).
    NOTE: Only available for Bootstrap 5 pages!

    Example:
        @use_tempusdominus
        def dispatch(self, request, *args, **kwargs):
            return super().dispatch(request, *args, **kwargs)

    Or alternatively:
        @method_decorator(use_tempusdominus, name='dispatch')
        class MyViewClass(MyViewSubclass):
            ...
    """
    return set_request_flag(view_func, 'use_tempusdominus')


def waf_allow(kind, hard_code_pattern=None):
    """
    Using this decorator simply registers a function for later use

    Since this is used to pull out metadata about our application,
    and not to modify the functioning of the application itself,
    there is no need to modify the function.

    Use this decorator like this

        @waf_allow('XSS_BODY')
        def my_view(...): ...

    to signify "if you put a WAF in front of this, make sure the XSS_BODY rule does not BLOCK this url pattern"

    For super abstracted setups where getting at the original view is hard
    you can use

        waf_allow('XSS_BODY', hard_code_pattern=r'/url/regex/')

    instead.
    """
    if hard_code_pattern:
        waf_allow.views[kind].add(hard_code_pattern)
        return

    def inner(fn):
        waf_allow.views[kind].add(fn)
        return fn
    return inner


waf_allow.views = defaultdict(set)


def set_request_flag(view_func, attr_name, attr_value=True):
    def _set_attr(request):
        setattr(request, attr_name, attr_value)

    return get_wrapped_view(view_func, _set_attr)


def get_wrapped_view(view_func, request_modifier):
    @wraps(view_func)
    def _wrapped(*args, **kwargs):
        request = _get_request_from_args(*args, **kwargs)
        request_modifier(request)
        return view_func(*args, **kwargs)

    return _wrapped


def _get_request_from_args(*args, **kwargs):
    if hasattr(args[0], 'META'):
        # function view
        return args[0]
    else:
        # class view
        return args[1]
