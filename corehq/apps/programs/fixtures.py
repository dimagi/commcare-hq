from corehq.apps.programs.models import Program
from corehq.apps.commtrack.fixtures import _simple_fixture_generator


class ProgramFixturesProvider(object):
    id = 'commtrack:programs'

    def __call__(self, user, version, last_sync=None):
        fields = ('name', 'code')
        data_fn = lambda: Program.by_domain(user.domain)
        return _simple_fixture_generator(user, self.id, "program", fields, data_fn, last_sync)

program_fixture_generator = ProgramFixturesProvider()
