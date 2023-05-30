import re
from django.utils.html import format_html_join


def safe_replace(pattern, replace_fun, raw_string):
    """
    Runs all matches found in raw_string through replace_fun, ensuring that all parts of this
    new string are sanitized for HTML display
    """
    current_index = 0
    tokens = []
    for match in re.finditer(pattern, raw_string):
        previous_chars = raw_string[current_index:match.start()]
        if previous_chars:
            tokens.append(previous_chars)
        tokens.append(replace_fun(match))
        current_index = match.end()

    remainder = raw_string[current_index:]
    if remainder:
        tokens.append(remainder)

    return format_html_join('', '{}', ((token,) for token in tokens))
