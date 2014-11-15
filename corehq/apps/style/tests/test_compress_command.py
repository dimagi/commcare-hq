from django.core.management import call_command
from django.test import SimpleTestCase


class TestDjangoCompressOffline(SimpleTestCase):

    def test_compress_offline(self):
        call_command('compress', force=True)
