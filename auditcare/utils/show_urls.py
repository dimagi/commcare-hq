#from http://code.activestate.com/recipes/576974-show-all-url-patterns-in-django/
#prints a tree of all the urls in the project
import pdb
from types import FunctionType

def show_urls(urllist, depth=0):
    ret = []
    for entry in urllist:
#        '__class__', '__delattr__', '__dict__', '__doc__', '__format__', '__getattribute__', '__hash__', '__init__', '__module__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_callback', '_callback_str', '_get_callback', 'add_prefix', 'callback', 'default_args', 'name', 'regex', 'resolve'
        props = dir(entry)
        #for p in props:
            #print "\t%s: %s" % (p, getattr(entry, p))
        if hasattr(entry, '_callback_str'):
            #print entry
            ret.append((entry.regex.pattern, entry._callback_str))
        else:
            print entry
            if isinstance(entry.callback, FunctionType):
                #print entry.callback
#                print dir(entry.callback)
                callback_str = "%s.%s" % (entry.callback.__module__, entry.callback.func_name)
                ret.append((entry.regex.pattern, callback_str))
        if hasattr(entry, 'url_patterns'):
            ret.extend(show_urls(entry.url_patterns, depth + 1))
    return ret

#show_urls(urls.urlpatterns)