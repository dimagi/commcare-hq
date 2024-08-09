
def nottest(fn):
    fn.__test__ = False
    return fn


def istest(fn):
    fn.__test__ = True
    return fn
