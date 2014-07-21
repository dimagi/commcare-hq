def use_bootstrap_3():
    def decorate(fn):
        """
        Decorator to Toggle on the use of bootstrap 3.
        """
        def wrapped(request, *args, **kwargs):
            request.use_bootstrap_3 = True
            return fn(request, *args, **kwargs)
        return wrapped
    return decorate
