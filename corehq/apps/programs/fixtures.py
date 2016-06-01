from corehq.apps.programs.models import Program
from corehq.apps.commtrack.fixtures import _simple_fixture_generator

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
        'structure': {
            f: {
                'name': f,
                'no_option': True
            } for f in fields},

        # DEPRECATED PROPERTIES
        'sourceUri': uri,
        'defaultId': 'programs',
        'initialQuery': "instance('programs')/programs/program",
    }


class ProgramFixturesProvider(object):
    id = 'commtrack:programs'

    def __call__(self, user, version, last_sync=None, app=None):
        data_fn = lambda: Program.by_domain(user.domain)
        return _simple_fixture_generator(user, self.id, "program",
                                         PROGRAM_FIELDS, data_fn, last_sync)

program_fixture_generator = ProgramFixturesProvider()
