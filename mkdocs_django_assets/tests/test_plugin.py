import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from mkdocs_django_assets.mkdocs_django_assets.plugin import DjangoAssetsPlugin


@pytest.fixture
def selections_md_content():
    md_path = Path(__file__).resolve().parents[2] / 'docs' / 'styleguide' / 'selections.md'
    assert md_path.exists(), f"Missing test input markdown: {md_path}"
    return md_path.read_text(encoding='utf-8')


def make_fake_page(src_path: str = 'selections.md', title: str = 'Selections'):
    file_ns = SimpleNamespace(src_path=src_path)
    page_ns = SimpleNamespace(file=file_ns, title=title)
    return page_ns


def test_on_post_page_replaces_components_with_iframes(selections_md_content):
    plugin = DjangoAssetsPlugin()

    # Call on_post_page with a minimal fake page (MkDocs passes a Page object; we only need file.src_path and title)
    output = plugin.on_post_page(selections_md_content, page=make_fake_page())

    # It should replace component placeholders with iframes
    assert 'django-example-component' not in output, 'Component placeholders were not fully replaced'
    assert '<iframe ' in output, 'Expected at least one iframe to be inserted'

    # Should contain fixed height styling per current implementation
    assert 'height:500px' in output, 'Iframe height should be fixed at 500px'

    # The iframe srcdoc should include assets from the selections base page (webpack entry)
    # Hashes change, so check a stable substring
    assert 'styleguide/js/selections' in output, 'Expected selections JS bundle reference in iframe srcdoc'

    # Sanity: base template head and body should be included
    assert '<head>' not in selections_md_content  # original md has no head
    assert 'srcdoc=' in output  # final output uses srcdoc in iframes

