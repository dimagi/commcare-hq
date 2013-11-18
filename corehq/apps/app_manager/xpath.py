import re


def dot_interpolate(xpath, context):
    """
    Replaces non-decimal dots in `context` with `xpath`
    """
    pattern = r'(\D|^)\.(\D|$)'
    repl = '\g<1>%s\g<2>' % xpath
    return re.sub(pattern, repl, context)
