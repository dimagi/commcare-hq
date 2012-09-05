def inline(fn):
    """
    decorator used to call a function in place
    similar to JS `var user_id = (function () { ... }());`

    example:

        @inline
        def user_id():
            if request.couch_user.is_commcare_user():
                return request.couch_user.get_id
            else:
                return request.GET.get('user_id')

    """
    return fn()
