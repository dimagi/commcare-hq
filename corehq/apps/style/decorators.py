from corehq import toggles


def preview_boostrap3():
    def decorate(fn):
        """
        Decorator to Toggle on the use of bootstrap 3.
        """
        def wrapped(request, *args, **kwargs):
            request.preview_bootstrap3 = (
                hasattr(request, 'user')
                and toggles.BOOTSTRAP3_PREVIEW.enabled(request.user.username))
            return fn(request, *args, **kwargs)
        return wrapped
    return decorate
