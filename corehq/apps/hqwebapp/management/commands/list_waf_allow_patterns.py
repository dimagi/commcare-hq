import re

from django.core.management import BaseCommand
from django.urls import get_resolver

from corehq.apps.hqwebapp.decorators import waf_allow


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--compact',
            action='store_true',
            default=False,
            help='Compact multiple regular expressions into regexes no longer than 200 chars each',
        )

    def handle(self, *args, compact=False, **options):
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
            if not compact:
                for pattern in patterns:
                    print(pattern)
            else:
                buffer = ''
                for pattern in patterns:
                    if len(buffer) + len(pattern) + 1 <= 200:
                        if buffer:
                            buffer += '|' + pattern
                        else:
                            buffer = pattern
                    else:
                        print(buffer)
                        buffer = pattern
                if buffer:
                    print(buffer)


def _remove_regex_groups(regex_string):
    return re.sub(r'\?P<[^>]+>', '', regex_string)
