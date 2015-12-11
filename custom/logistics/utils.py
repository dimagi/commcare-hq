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


def get_username_for_user(domain, smsuser, username_part=None):
        domain_part = "%s.commcarehq.org" % domain

        if not username_part:
            username_part = "%s%d" % (smsuser.name.strip().replace(' ', '.').lower(),
                                      smsuser.id)
        return "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part), username_part
