from functools import wraps


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


def use_angular_js(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the angularjs library at the base template
    level.

    Example:

    @use_angular_js
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_angular_js = True
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
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_multiselect = True
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


def use_maps_async(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the inclusion of the maps (with async utils) library at the base
    template level.

    Example:

    @use_maps_async
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_maps_async = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped


def maps_prefer_canvas(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to set L_PREFER_CANVAS = true; before including the maps library.

    Example:

    @maps_prefer_canvas
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.maps_prefer_canvas = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped
