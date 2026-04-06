import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from corehq.apps.hqmedia.utils import save_multimedia_upload


class TestSaveMultimediaUpload(SimpleTestCase):

    def _make_zip_file(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('images/icon.png', b'\x89PNG fake data')
        buf.seek(0)
        buf.name = 'multimedia.zip'
        return buf

    @patch('corehq.apps.hqmedia.utils.expose_cached_download')
    def test_returns_processing_id(self, mock_expose):
        mock_saved = MagicMock()
        mock_saved.download_id = 'dl-abc123'
        mock_expose.return_value = mock_saved

        uploaded_file = self._make_zip_file()
        processing_id, status = save_multimedia_upload(uploaded_file)
        self.assertEqual(processing_id, 'dl-abc123')
        self.assertIsNotNone(status)
        mock_expose.assert_called_once()

    @patch('corehq.apps.hqmedia.utils.expose_cached_download')
    def test_reads_file_content(self, mock_expose):
        mock_saved = MagicMock()
        mock_saved.download_id = 'dl-abc123'
        mock_expose.return_value = mock_saved

        uploaded_file = self._make_zip_file()
        save_multimedia_upload(uploaded_file)

        call_args = mock_expose.call_args
        self.assertIsInstance(call_args[0][0], bytes)
