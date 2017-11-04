from functools import wraps


def use_new_analytics(view_func):
    """Use this decorator on the dispatch method of a TemplateView subclass
    to enable the use of the new analytics library on that view.

    Example:

    @use_new_analytics
    def dispatch(self, request, *args, **kwargs):
        return super(MyView, self).dispatch(request, *args, **kwargs)
    """
    @wraps(view_func)
    def _wrapped(class_based_view, request, *args, **kwargs):
        request.use_new_analytics = True
        return view_func(class_based_view, request, *args, **kwargs)
    return _wrapped
