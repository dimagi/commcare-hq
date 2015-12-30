from StringIO import StringIO
from mock import patch, MagicMock

from compressor.offline.django import DjangoParser
from django.conf import settings
from django.template.loader_tags import ExtendsNode
from django.core.management import call_command
from django.test import SimpleTestCase
from unittest.util import safe_repr

BLOCK_JS = ' block js '
BLOCK_CSS = ' block stylesheets '
ENDBLOCK = ' endblock '

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
        if 'src' not in line and 'href' not in line:
            return
        self.assertIn(
            'new_static', line, msg='new_static not found in %s in file %s' % (safe_repr(line), filename)
        )

    def _is_b3(self, filename):
        if filename in IGNORED_FILES:
            return  False
        parser = DjangoParser(charset=settings.FILE_CHARSET)
        template = parser.parse(filename)

        return self._is_b3_base_template(template)

    def _is_b3_base_template(self, template):
        if template.name == 'style/bootstrap3/base.html':
            return True

        nodes = list(template.nodelist)
        for node in nodes:
            if isinstance(node, ExtendsNode):
                # Get parent requires a context variable, just pass in mock to make it work
                return self._is_b3_base_template(node.get_parent(MagicMock()))

        return False

    def test_compress_offline(self):
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
                        if (BLOCK_JS in line or BLOCK_CSS in line) and ENDBLOCK not in line:
                            in_compress_block = True
                            continue

                        if ENDBLOCK in line:
                            in_compress_block = False

                        if in_compress_block:
                            self._assert_valid_import(line, filename)
