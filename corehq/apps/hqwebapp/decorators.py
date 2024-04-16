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

    @wraps(view_func)
    def _wrapped(*args, **kwargs):
        if hasattr(args[0], 'META'):
            # function view
            request = args[0]
        else:
            # class view
            request = args[1]
        request.use_daterangepicker = True
        return view_func(*args, **kwargs)
    return _wrapped


def use_jquery_ui(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the jquery-ui library at the base template
    level.

    Example:

    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_jquery_ui = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_multiselect(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the multiselect library at the base template
    level.

    Example:

    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(*args, **kwargs):
        if hasattr(args[0], 'META'):
            # function view
            request = args[0]
        else:
            # class view
            request = args[1]
        request.use_multiselect = True
        return view_func(*args, **kwargs)
    return _wrapped


def use_nvd3(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the nvd3 library at the base template
    level. nvd3 is a library of charts for d3.

    Example:

    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_nvd3 = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_nvd3_v3(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the nvd3 library at the base template
    level. nvd3 Version 3 is a library of charts for d3.

    Example:

    @use_nvd3
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_nvd3_v3 = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_timeago(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the timeago library at the base template
    level.

    Example:

    @use_timeago
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_timeago = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_datatables(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the datatables library at the base template
    level.

    Example:

    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_datatables = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_typeahead(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the typeahead library at the base template
    level.

    Example:

    @use_typeahead
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_typeahead = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_timepicker(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the timepicker library at the base template
    level.

    Example:

    @use_timepicker
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_timepicker = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_maps(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the maps (with sync utils) library at the base
    template level.

    Example:

    @use_maps
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_maps = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_ko_validation(view_func):
    """Use this decorator to use knockout validation in knockout forms

    Example Tag Usage:

    @use_ko_validation
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_ko_validation = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


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
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        set_bootstrap_version5()
        return view_func(request, *args, **kwargs)
    return _inner


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
    @wraps(view_func)
    def _inner(request, *args, **kwargs):
        request.use_tempusdominus = True
        return view_func(request, *args, **kwargs)
    return _inner


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
