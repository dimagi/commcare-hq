import tempfile
from contextlib import contextmanager
from typing import Iterator

from corehq.apps.users.models import CommCareUser


@contextmanager
def get_temp_filename(content: str) -> Iterator[str]:
    with tempfile.NamedTemporaryFile(mode='w', newline='') as temp_file:
        temp_file.write(content)
        temp_file.flush()
        yield temp_file.name


@contextmanager
def get_test_user(domain: str, username: str) -> Iterator[CommCareUser]:
    user = CommCareUser.create(domain, username, '*****', None, None)
    try:
        yield user
    finally:
        user.delete(None, deleted_by=None)
