import fluff


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)