from io import BytesIO
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from corehq.messaging.scheduling.models.content import EmailContent, EmailImage
from corehq.messaging.scheduling.tasks import delete_unused_messaging_images
from corehq.util.test_utils import flag_enabled


class MessagingImageUploadTest(TestCase):
    def test_delete_unused_messaging_images(self):
        fake_image = BytesIO(b"123")
        delete_after = datetime.utcnow() + timedelta(days=1)
        used_image = EmailImage.save_blob(
            fake_image,
            domain="fake",
            filename="used.jpg",
            content_type="image/jpg",
            delete_after=delete_after,
        )
        self.addCleanup(used_image.delete)
        unused_image = EmailImage.save_blob(
            fake_image,
            domain="fake",
            filename="unused.jpg",
            content_type="image/jpg",
            delete_after=delete_after,
        )
        self.addCleanup(unused_image.delete)

        html_message = {"*": f'<img src="{used_image.get_url()}" />'}

        content = EmailContent.objects.create(
            subject="Test Email with Images", message="", html_message=html_message
        )
        self.addCleanup(content.delete)

        self.assertEqual(len(EmailImage.get_all()), 2)
        delete_unused_messaging_images()
        remaining_images = EmailImage.get_all()
        self.assertEqual(len(remaining_images), 1)
        self.assertEqual(remaining_images[0].filename, "used.jpg")
