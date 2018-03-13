from __future__ import absolute_import
from __future__ import unicode_literals
import os
from nose.plugins.attrib import attr

from django.test import SimpleTestCase

from django.conf import settings
from django.template.loaders.app_directories import get_app_template_dirs

B3_BASE = 'hqwebapp/base.html'

COMPRESS_JS = ' compress js '
COMPRESS_CSS = ' compress css '
ENDCOMPRESS = ' endcompress '

DISALLOWED_TAGS = [
    ('{% if', 'You cannot use "if" tags in a compress block'),
    ('^</script>$', 'You cannot use inline JS in a compress block'),
]

IGNORED_FILES = [
    'http://opensource.org/licenses/mit-license.html',
    'More Info : http://www.quirksmode.org/css/box.html',
]


class TestDjangoCompressOffline(SimpleTestCase):

    def _assert_valid_import(self, line, filename):
        if not line.strip():
            return
        for tag in DISALLOWED_TAGS:
            self.assertNotRegexpMatches(line.strip(), tag[0], '{}: {}'.format(tag[1], filename))

    @attr("slow")
    def test_compress_offline(self):
        in_compress_block = False

        template_dir_list = []
        for template_dir in get_app_template_dirs('templates'):
            if settings.BASE_DIR in template_dir:
                template_dir_list.append(template_dir)

        template_list = []
        for template_dir in template_dir_list:
            for base_dir, dirnames, filenames in os.walk(template_dir):
                for filename in filenames:
                    template_list.append(os.path.join(base_dir, filename))

        # Filter lines that are not html and strip whitespace
        filenames = [name for name in [name.strip() for name in template_list] if name.endswith('.html')]

        for filename in filenames:
            with open(filename, 'r') as f:
                in_compress_block = False
                for line in f.readlines():
                    has_start_tag = COMPRESS_JS in line or COMPRESS_CSS in line
                    has_end_tag = ENDCOMPRESS in line

                    if has_start_tag and not has_end_tag:
                        in_compress_block = True
                        continue

                    if has_end_tag:
                        in_compress_block = False

                    if in_compress_block:
                        self._assert_valid_import(line, filename)
