from StringIO import StringIO
from mock import patch, MagicMock

from compressor.offline.django import DjangoParser
from django.conf import settings
from django.template.loader_tags import ExtendsNode
from django.core.management import call_command
from django.test import SimpleTestCase
from nose.plugins.attrib import attr
from unittest.util import safe_repr

B3_BASE = 'style/bootstrap3/base.html'

BLOCK_JS = ' block js '
BLOCK_CSS = ' block stylesheets '
ENDBLOCK = ' endblock '

COMPRESS_JS = ' compress js '
COMPRESS_CSS = ' compress stylesheets '
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
            self.assertNotRegexpMatches(tag[0], line.strip(), tag[1])

    def _is_b3(self, filename):
        if filename in IGNORED_FILES:
            return False

        if filename.endswith(B3_BASE):
            return True

        parser = DjangoParser(charset=settings.FILE_CHARSET)
        template = parser.parse(filename)

        return self._is_b3_base_template(template)

    def _is_b3_base_template(self, template):
        if template.name == B3_BASE:
            return True

        nodes = list(template.nodelist)
        for node in nodes:
            if isinstance(node, ExtendsNode):
                # Get parent requires a context variable, just pass in mock to make it work
                return self._is_b3_base_template(node.get_parent(MagicMock()))

        return False

    @attr("slow")
    def test_compress_offline(self):
        call_command('collectstatic', verbosity=0, interactive=False)
        call_command('fix_less_imports_collectstatic', verbosity=0, interactive=False)
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            call_command('compress', force=True)

            mock_stdout.seek(0)
            filenames = mock_stdout.readlines()

        in_compress_block = False

        # Filter lines that are not html and strip whitespace
        filenames = filter(lambda name: name.endswith('.html'), map(lambda name: name.strip(), filenames))

        for filename in filenames:
            if self._is_b3(filename):
                with open(filename, 'r+') as f:
                    for line in f.readlines():
                        has_start_tag = BLOCK_JS in line or BLOCK_CSS in line
                        has_start_tag = has_start_tag or COMPRESS_JS in line or COMPRESS_CSS in line
                        has_end_tag = ENDBLOCK in line or ENDCOMPRESS in line

                        if has_start_tag and not has_end_tag:
                            in_compress_block = True
                            continue

                        if has_end_tag:
                            in_compress_block = False

                        if in_compress_block:
                            self._assert_valid_import(line, filename)
