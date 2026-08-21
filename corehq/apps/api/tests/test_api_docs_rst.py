"""The toctree must not name a page that does not exist, and must not
leave a page unreachable."""
import pathlib

import pytest

DOCS_API = (
    pathlib.Path(__file__).resolve().parents[4] / 'docs' / 'api'
)


def test_the_docs_api_directory_was_found():
    """Guards the parents[4] hop above: if this file moves, every other
    test in here would pass vacuously on an empty glob."""
    assert (DOCS_API / 'index.rst').exists(), DOCS_API


def _toctree_entries():
    """Every page named across all of index.rst's toctrees.

    The file has four, with prose between them, so the end of a block is
    tracked per block: a blank line closes a toctree only once that block
    has named at least one page, since a blank line also follows the
    ``:maxdepth:`` option line.
    """
    entries = []
    in_tree = False
    named_in_block = False
    for line in (DOCS_API / 'index.rst').read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith('.. toctree::'):
            in_tree, named_in_block = True, False
            continue
        if not in_tree:
            continue
        if stripped.startswith(':'):
            continue
        if not stripped:
            if named_in_block:
                in_tree = False
            continue
        if not line.startswith(' '):
            in_tree = False
            continue
        entries.append(stripped)
        named_in_block = True
    return entries


def test_every_toctree_entry_exists():
    missing = [e for e in _toctree_entries()
               if not (DOCS_API / f'{e}.rst').exists()]
    assert not missing, f'toctree names pages that do not exist: {missing}'


def test_every_page_is_in_the_toctree():
    entries = set(_toctree_entries())
    pages = {p.stem for p in DOCS_API.glob('*.rst')} - {'index'}
    assert not pages - entries, f'pages missing from the toctree: {pages - entries}'


@pytest.mark.parametrize('page', sorted(
    p for p in (x.stem for x in DOCS_API.glob('*.rst')) if p != 'index'
))
def test_page_is_not_empty(page):
    assert (DOCS_API / f'{page}.rst').read_text().strip(), f'{page}.rst is empty'
