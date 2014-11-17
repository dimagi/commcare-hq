from corehq.apps.programs.models import Program
from corehq.apps.commtrack.fixtures import _simple_fixture_generator


def program_fixture_generator(user, version, case_sync_op=None, last_sync=None):
    fields = [
        'name',
        'code'
    ]
    data_fn = lambda: Program.by_domain(user.domain)
    return _simple_fixture_generator(user, "program", fields, data_fn, last_sync)
