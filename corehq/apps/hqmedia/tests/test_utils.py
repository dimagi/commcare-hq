import zipfile
from io import BytesIO
from unittest.mock import MagicMock, patch

from corehq.apps.hqmedia.utils import save_multimedia_upload


def _make_zip_file():
    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('images/icon.png', b'\x89PNG fake data')
    buf.seek(0)
    buf.name = 'multimedia.zip'
    return buf


@patch('corehq.apps.hqmedia.utils.BulkMultimediaStatusCache')
@patch('corehq.apps.hqmedia.utils.expose_cached_download')
def test_save_multimedia_upload_returns_processing_id(mock_expose, mock_cache_cls):
    mock_saved = MagicMock()
    mock_saved.download_id = 'dl-abc123'
    mock_expose.return_value = mock_saved

    processing_id, status = save_multimedia_upload(_make_zip_file())

    assert processing_id == 'dl-abc123'
    assert status is not None
    mock_expose.assert_called_once()


@patch('corehq.apps.hqmedia.utils.BulkMultimediaStatusCache')
@patch('corehq.apps.hqmedia.utils.expose_cached_download')
def test_save_multimedia_upload_reads_file_content(mock_expose, _mock_cache_cls):
    mock_saved = MagicMock()
    mock_saved.download_id = 'dl-abc123'
    mock_expose.return_value = mock_saved

    save_multimedia_upload(_make_zip_file())

    content = mock_expose.call_args[0][0]
    assert isinstance(content, bytes)
