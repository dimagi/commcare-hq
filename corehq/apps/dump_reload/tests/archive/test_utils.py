from corehq.apps.dump_reload.archive.utils import get_tmp_extract_dir


def test_get_tmp_extract_dir_default_specifier():
    assert get_tmp_extract_dir('data-dump-foo.zip') == '_tmp_load__data-dump-foo.zip'


def test_get_tmp_extract_dir_with_specifier():
    assert (
        get_tmp_extract_dir('data-dump-foo.zip', specifier='blob_meta')
        == '_tmp_load_blob_meta_data-dump-foo.zip'
    )
