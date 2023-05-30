from django.core.management import BaseCommand

from corehq.apps.settings.views import get_qrcode
from corehq.apps.settings.tests.test_views import TestQrCode


class Command(BaseCommand):
    help = """Writes new reference PNG file(s) (to make tests pass again)"""

    def handle(self, **options):
        with open(TestQrCode.TEST_QR_CODE_FILE, "wb") as png_out:
            png_out.write(get_qrcode(TestQrCode.TEST_QR_CODE_TEXT))
