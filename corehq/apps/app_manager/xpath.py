import re


def dot_interpolate(string, replacement):
    """
    Replaces non-decimal dots in `string` with `replacement`
    """
    pattern = r'(\D|^)\.(\D|$)'
    repl = '\g<1>%s\g<2>' % replacement
    return re.sub(pattern, repl, string)
