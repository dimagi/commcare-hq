from pathlib import Path

import pytest
from yaml import load, Loader, parser

REPORTS_DIR = Path(__file__).parent.parent


@pytest.mark.parametrize("filename", [p.name for p in REPORTS_DIR.glob('*.yml')])
def test_yaml_formatting(filename):
    with open(REPORTS_DIR / filename, 'r') as f:
        try:
            load(f.read(), Loader=Loader)
        except parser.ParserError:
            assert False  # the test runner will tell us which file, and what went wrong.
