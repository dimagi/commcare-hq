#Source: http://djangosnippets.org/snippets/1378/ which yielded: http://pastebin.com/raw.php?i=7KfALc0j
from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import RegexURLPattern, Resolver404, get_resolver

__all__ = ('resolve_to_name',)


def _pattern_resolve_to_name(self, path):
    match = self.regex.search(path)
    if match:
        name = ""
        if self.name:
            name = self.name
        elif hasattr(self, '_callback_str'):
            name = self._callback_str
        else:
            name = "%s.%s" % (self.callback.__module__, self.callback.__name__)
        return name


def _resolver_resolve_to_name(self, path):
    tried = []
    match = self.regex.search(path)
    if match:
        new_path = path[match.end():]
        for pattern in self.url_patterns:
            try:
                name = _pattern_resolve_to_name(pattern, new_path)
            except Resolver404 as e:
                tried.extend([(pattern.regex.pattern + '   ' + t) for t in e.args[0]['tried']])
            else:
                if name:
                    return name
                tried.append(pattern.regex.pattern)
        raise Resolver404({'tried': tried, 'path': new_path})


def resolve_to_name(path, urlconf=None):
    r = get_resolver(urlconf)
    if isinstance(r, RegexURLPattern):
        return _pattern_resolve_to_name(r, path)
    else:
        return _resolver_resolve_to_name(r, path)
