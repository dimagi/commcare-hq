from functools import wraps
from corehq.apps.style.utils import set_bootstrap_version3
from crispy_forms.utils import set_template_pack


def use_bootstrap3(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable Bootstrap3 features for the included template. This makes sure
    that all crispy forms are in Boostrap3 mode, for instance.

    Example:

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        # set bootstrap version in thread local
        set_bootstrap_version3()
        # set crispy forms template in thread local
        set_template_pack('bootstrap3')
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_select2(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the select2 js library at the base template.

    Example:

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_select2 = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_select2_v4(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the 4.0 Version of select2 js library at
    the base template. (4.0 is still in testing phase)

    Example:

    @use_select2_v4
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_select2_v4 = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def use_knockout_js(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the knockout_js library at the base template
    level.

    Example:

    @use_knockout_js
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_knockout_js = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def upgrade_knockout_js(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the knockout_js 3.1 library at the base template
    level, for bootstrap 2 templates (during phase out).

    Example:

    @upgrade_knockout_js
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.upgrade_knockout_js = True
        return view_func(class_based_view, request, *args, **kwargs)
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
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_daterangepicker = True
        return view_func(class_based_view, request, *args, **kwargs)
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

