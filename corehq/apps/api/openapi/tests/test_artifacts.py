import pytest

from corehq.apps.api.openapi import artifacts


def test_paths_are_under_the_repo():
    assert artifacts.spec_path('user-v1').name == 'user-v1.json'
    assert artifacts.spec_path('user-v1').parent == artifacts.SPEC_DIR
    assert artifacts.page_path('user-v1').name == 'user-v1.html'
    assert artifacts.page_path('user-v1').parent == artifacts.DIST_DIR


def test_read_spec_returns_a_generated_document():
    spec = artifacts.read_spec('user-v1')
    assert spec['openapi'] == '3.0.3'
    assert spec['paths']


def test_read_spec_is_none_for_an_ungenerated_slug():
    assert artifacts.read_spec('not-a-real-api') is None


def test_read_page_is_none_when_the_build_has_not_run(
    tmp_path, monkeypatch, request
):
    monkeypatch.setattr(artifacts, 'DIST_DIR', tmp_path)
    artifacts.read_page.cache_clear()
    request.addfinalizer(artifacts.read_page.cache_clear)
    assert artifacts.read_page('user-v1') is None


def test_read_page_returns_the_built_html(tmp_path, monkeypatch, request):
    (tmp_path / 'user-v1.html').write_text('<html>built</html>')
    monkeypatch.setattr(artifacts, 'DIST_DIR', tmp_path)
    artifacts.read_page.cache_clear()
    request.addfinalizer(artifacts.read_page.cache_clear)
    assert artifacts.read_page('user-v1') == '<html>built</html>'


def test_read_page_does_not_cache_a_miss(tmp_path, monkeypatch, request):
    monkeypatch.setattr(artifacts, 'DIST_DIR', tmp_path)
    artifacts.read_page.cache_clear()
    request.addfinalizer(artifacts.read_page.cache_clear)
    assert artifacts.read_page('late-v1') is None
    (tmp_path / 'late-v1.html').write_text('<html>built</html>')
    assert artifacts.read_page('late-v1') == '<html>built</html>'


def test_read_spec_does_not_cache_a_miss(tmp_path, monkeypatch, request):
    monkeypatch.setattr(artifacts, 'SPEC_DIR', tmp_path)
    artifacts.read_spec.cache_clear()
    request.addfinalizer(artifacts.read_spec.cache_clear)
    assert artifacts.read_spec('late-v1') is None
    (tmp_path / 'late-v1.json').write_text('{"openapi": "3.0.3"}')
    assert artifacts.read_spec('late-v1') == {'openapi': '3.0.3'}


def test_spec_content_hash_does_not_cache_a_miss(
    tmp_path, monkeypatch, request
):
    monkeypatch.setattr(artifacts, 'SPEC_DIR', tmp_path)
    artifacts.spec_content_hash.cache_clear()
    request.addfinalizer(artifacts.spec_content_hash.cache_clear)
    assert artifacts.spec_content_hash('late-v1') is None
    (tmp_path / 'late-v1.json').write_bytes(b'{}')
    assert artifacts.spec_content_hash('late-v1') is not None


def test_spec_content_hash_is_stable_and_slug_specific():
    first = artifacts.spec_content_hash('user-v1')
    assert first == artifacts.spec_content_hash('user-v1')
    assert first != artifacts.spec_content_hash('group-v1')


def test_documented_slugs_matches_the_catalogue():
    from corehq.apps.api.openapi.catalogue import documented_entries

    assert artifacts.documented_slugs() == {
        entry.doc_slug for entry in documented_entries()
    }


@pytest.mark.parametrize('slug', ['user-v1', 'case-v1', 'group-v1'])
def test_fully_documented_apis_report_complete_coverage(slug):
    described, total = artifacts.description_coverage(slug)
    assert total > 0
    assert described == total


def test_undescribed_api_reports_incomplete_coverage():
    described, total = artifacts.description_coverage('application-v1')
    assert total > 0
    assert described < total


def test_coverage_counts_each_property_once():
    # user-v1 has a list and a detail endpoint over the same record, so a
    # naive count would double every field.
    described, total = artifacts.description_coverage('user-v1')
    spec = artifacts.read_spec('user-v1')
    schema = spec['paths']['/a/{domain}/api/user/v1/']['get']['responses'][
        '200'
    ]['content']['application/json']['schema']
    fields = schema['properties']['objects']['items']['properties']
    assert total == len(fields)


def test_coverage_is_zero_for_an_unknown_slug():
    assert artifacts.description_coverage('not-a-real-api') == (0, 0)
