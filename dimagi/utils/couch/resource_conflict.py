from couchdbkit.exceptions import ResourceConflict

def repeat(fn, n):
    for _ in range(n):
        try:
            return fn()
        except ResourceConflict:
            pass