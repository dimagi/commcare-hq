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

        project = restore_user.project
        if not project or not project.commtrack_enabled:
            return []

        data = Program.by_domain(restore_user.domain)

        if not self._should_sync(data, restore_state.last_sync_log):
            return []

        return simple_fixture_generator(
            restore_user, self.id, "program",
            PROGRAM_FIELDS, data
        )

    def _should_sync(self, data, last_sync):
        """
        Determine if a data collection needs to be synced.
        """

        # definitely sync if we haven't synced before
        if not last_sync or not last_sync.date:
            return True

        # check if any items have been modified since last sync
        for data_item in data:
            # >= used because if they are the same second, who knows
            # which actually happened first
            if not data_item.last_modified or data_item.last_modified >= last_sync.date:
                return True

        return False


program_fixture_generator = ProgramFixturesProvider()
