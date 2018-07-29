from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.programs.models import Program
from corehq.apps.commtrack.fixtures import simple_fixture_generator

PROGRAM_FIELDS = ['name', 'code']


def program_fixture_generator_json(domain):
    if Program.by_domain(domain).count() == 0:
        return None

    fields = list(PROGRAM_FIELDS)
    fields.append('@id')

    uri = 'jr://fixture/{}'.format(ProgramFixturesProvider.id)
    return {
        'id': 'programs',
        'uri': uri,
        'path': '/programs/program',
        'name': 'Programs',
        'structure': {f: {'name': f, 'no_option': True} for f in fields},
    }


class ProgramFixturesProvider(FixtureProvider):
    id = 'commtrack:programs'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user

        data_fn = lambda: Program.by_domain(restore_user.domain)
        return simple_fixture_generator(
            restore_user, self.id, "program",
            PROGRAM_FIELDS, data_fn, restore_state.last_sync_log
        )

program_fixture_generator = ProgramFixturesProvider()
