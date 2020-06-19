import re

from django.core.management import BaseCommand
from django.urls import get_resolver

from corehq.apps.hqwebapp.decorators import waf_allow


class Command(BaseCommand):

    def handle(self, *args, **options):
        resolver = get_resolver()
        for kind, views in waf_allow.views.items():
            print(kind)
            print('--------')
            patterns = []
            for view in views:
                if isinstance(view, str):
                    # waf_allow(kind, hard_code_pattern=r'^/url/pattern/$')
                    patterns.append(view)
                else:
                    # @waf_allow(kind)
                    for urlmatch in resolver.reverse_dict.getlist(view):
                        patterns.append(resolver.regex.pattern + urlmatch[1])
            patterns = sorted(_remove_regex_groups(pattern) for pattern in patterns)
            for pattern in patterns:
                print(pattern)


def _remove_regex_groups(regex_string):
    return re.sub(r'\?P<[^>]+>', '', regex_string)
