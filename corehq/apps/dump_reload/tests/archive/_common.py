import os
import tempfile
from pathlib import Path

from unmagic import fixture


@fixture
def tmp_work_dir():
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield Path(tmp)
        finally:
            os.chdir(original)
