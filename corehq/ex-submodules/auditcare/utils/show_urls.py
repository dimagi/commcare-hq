# from http://code.activestate.com/recipes/576974-show-all-url-patterns-in-django/
# prints a tree of all the urls in the project
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from types import FunctionType


def show_urls(urllist, depth=0):
    ret = []
    for entry in urllist:
        if hasattr(entry, '_callback_str'):
            ret.append((entry.regex.pattern, entry._callback_str))
        else:
            print(entry)
            if isinstance(entry.callback, FunctionType):
                callback_str = "%s.%s" % (entry.callback.__module__, entry.callback.__name__)
                ret.append((entry.regex.pattern, callback_str))
        if hasattr(entry, 'url_patterns'):
            ret.extend(show_urls(entry.url_patterns, depth + 1))
    return ret
