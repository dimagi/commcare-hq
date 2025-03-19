from django.test import SimpleTestCase

from couchforms.const import VALID_ATTACHMENT_FILE_EXTENSIONS


class TestCont(SimpleTestCase):
    def test_valid_attachment_file_extensions(self):
        self.assertSetEqual(
            VALID_ATTACHMENT_FILE_EXTENSIONS,
            {
                "jpg", "jpeg", "3gpp", "3gp", "3ga", "3g2", "mp3",
                "wav", "amr", "mp4", "3gp2", "mpg4", "mpeg4",
                "m4v", "mpg", "mpeg", "qcp", "ogg",
                "png", "pdf"
            }
        )
