def iterate_over_api_objects(func, filters=None):
    filters = filters or {}
    offset = 0
    limit = 100
    _, objects = func(limit=limit, offset=offset, filters=filters)
    while objects:
        for obj in objects:
            yield obj

        offset += 100
        _, objects = func(limit=limit, offset=offset, filters=filters)
