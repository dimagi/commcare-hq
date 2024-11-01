def raise_after_max_elements(it, max_elements, exception=None):
    for total_yielded, ele in enumerate(it):
        if total_yielded >= max_elements:
            exception = exception or Exception('Too Many Elements')
            raise exception

        yield ele
