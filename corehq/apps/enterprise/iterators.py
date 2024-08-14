def raise_after_max_elements(it, max_elements, exception=None):
    total_yielded = 0
    for ele in it:
        if total_yielded >= max_elements:
            exception = exception or Exception('Too Many Elements')
            raise exception

        yield ele
        total_yielded += 1
