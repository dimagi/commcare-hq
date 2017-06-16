from dimagi.utils.decorators.memoized import memoized
from custom.enikshay.case_utils import get_person_case_from_episode
from casexml.apps.case.xform import get_case_updates


class EpisodeFacilityIDMigration(object):
    """https://docs.google.com/document/d/1w6T1ShTdZCB1UZjogckh1uBUYynMUOY-OfOi5d4IFt8/edit#
    """

    def __init__(self, domain, episode_case):
        self.domain = domain
        self.episode = episode_case
        self.person = get_person_case_from_episode(self.domain, self.episode.case_id)

    @memoized
    def _person_actions(self):
        return self.person.actions

    def update_json(self):
        if not self._should_update:
            return {}

        return {
            'diagnosing_facility_id': self.diagnosing_facility_id,
            'treatment_initiating_facility_id': self.treatment_initiating_facility_id,
            'facility_id_migration_complete': 'true',
        }

    @property
    def should_update(self):
        return (
            self.episode.get_case_property('episode_type') == 'confirmed_tb'
            and (
                self.episode.get_case_property('facility_id_migration_complete') != 'true'
                or (
                    not self.episode.get_case_property('treatment_initiating_facility_id')
                    and not self.episode.get_case_property('diagnosing_facility_id')
                )
            )
        )

    @property
    def diagnosing_facility_id(self):
        """the owner_id of the person case at the time that the episode case with
        episode_type = 'confirmed_tb' was created (i.e., ignoring any changes of
        ownership that may have taken place since)

        """
        return self.find_owner_id_when_case_property_changed('current_episode_type', 'confirmed_tb')

    @property
    def treatment_initiating_facility_id(self):
        """the owner_id of the person case at the time that the Treatment Card is
        filled (i.e. when 'episode_pending_registration' gets set to 'no')

        """
        if self.episode.get_case_property('treatment_initiated') not in ('yes_phi', 'yes_private'):
            return None
        return self.find_owner_id_when_case_property_changed('episode_pending_registration', 'no')

    def find_owner_id_when_case_property_changed(self, case_property, value):
        """Finds the owner of the case at the time a specific case property was changed to a specific value

        """
        find_owner_id_at_index = self._get_index_to_find_owner_id(case_property, value)
        return self._get_owner_id_from_specific_index(find_owner_id_at_index)

    def _get_index_to_find_owner_id(self, case_property, value):
        """Find which transaction our specific case property changed in.

        This is the index from which we should check our owner_id

        """
        find_owner_id_at_index = None
        for i, transactions in enumerate(self._person_actions()):
            if self._property_changed_in_action(transactions, case_property) == value:
                find_owner_id_at_index = i
                break
        return find_owner_id_at_index

    def _get_owner_id_from_specific_index(self, index):
        """Given an index, go back in time and find the first action where the owner_id changes

        This will be the owner_id of the case at that point in time we are looking for.

        """
        if index is None:
            return None

        for transaction in self._person_actions()[index::-1]:
            owner_id = self._get_owner_id_from_transaction(transaction)
            if owner_id:
                return owner_id

        return None

    def _property_changed_in_action(self, action, case_property):
        update_actions = [update.get_update_action() for update in get_case_updates(action.form)]
        for action in update_actions:
            property_changed = action.dynamic_properties.get(case_property)
            if property_changed:
                return property_changed
        return False

    def _get_owner_id_from_transaction(self, transaction):
        case_updates = get_case_updates(transaction.form)
        update_actions = [update.get_update_action() for update in case_updates]
        create_actions = [update.get_create_action() for update in case_updates]
        all_actions = update_actions + create_actions  # look through updates first, as these trump creates
        for action in all_actions:
            if action:
                owner_id = action.get_known_properties().get('owner_id')
                if owner_id:
                    return owner_id
        return None
