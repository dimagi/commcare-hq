"""Example request and response payloads for the generated specs.

Kept out of the path builders: both need it, and neither should have to
import the other to get it.
"""

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / 'examples'


def load_example(relative_path):
    return json.loads((EXAMPLES_DIR / relative_path).read_text())
