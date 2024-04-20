
def nottest(fn):
    fn.__test__ = False
    return fn
