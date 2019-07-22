from __future__ import absolute_import
from __future__ import unicode_literals

from functools import partial

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.utils import get_or_cache_global_fixture, GLOBAL_USER_ID
from corehq.apps.programs.models import Program
from corehq.apps.commtrack.fixtures import simple_fixture_generator

PROGRAM_FIELDS = ['name', 'code']

PROGRAM_FIXTURE_BUCKET = 'program_fixture'


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
        # disable caching temporarily
        # https://dimagi-dev.atlassian.net/browse/IIO-332
        # data_fn = partial(self._get_fixture_items, restore_state)
        # return get_or_cache_global_fixture(restore_state, PROGRAM_FIXTURE_BUCKET, self.id, data_fn)
        return self._get_fixture_items(restore_state)

    def _get_fixture_items(self, restore_state):
        restore_user = restore_state.restore_user

        def get_programs():
            return Program.by_domain(restore_user.domain)

        return simple_fixture_generator(
            restore_user, self.id, "program",
            PROGRAM_FIELDS, get_programs, restore_state.last_sync_log
        )


program_fixture_generator = ProgramFixturesProvider()
