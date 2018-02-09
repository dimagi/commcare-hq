from __future__ import absolute_import
from django.utils.dateparse import parse_datetime

from dimagi.utils.decorators.memoized import memoized
from collections import namedtuple
from custom.enikshay.case_utils import get_person_case_from_episode
from casexml.apps.case.xform import get_case_updates

PropertyChangedInfo = namedtuple("PropertyChangedInfo", 'new_value modified_on')


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

    @memoized
    def _episode_actions(self):
        return self.episode.actions

    def update_json(self):
        if not self.should_update:
            return {}

        update = {
            'facility_id_migration_v2_complete': 'true',
        }

        diagnosing_facility_id = self.episode.get_case_property('diagnosing_facility_id')
        if ((diagnosing_facility_id is None or diagnosing_facility_id == '') and self.diagnosing_facility_id):
            update['diagnosing_facility_id'] = self.diagnosing_facility_id

        treatment_initiating_facility_id = self.episode.get_case_property('treatment_initiating_facility_id')
        if ((treatment_initiating_facility_id is None or treatment_initiating_facility_id == '')
           and self.treatment_initiating_facility_id):
            update['treatment_initiating_facility_id'] = self.treatment_initiating_facility_id

        return update

    @property
    def should_update(self):
        if self.episode.get_case_property('facility_id_migration_v2_complete') == 'true':
            return False

        diagnosing_facility_id = self.episode.get_case_property('diagnosing_facility_id')
        treatment_initiating_facility_id = self.episode.get_case_property('treatment_initiating_facility_id')
        if (diagnosing_facility_id is not None
           and diagnosing_facility_id != u''
           and treatment_initiating_facility_id is not None
           and treatment_initiating_facility_id != u'') or (
                '_archive_' in [diagnosing_facility_id, treatment_initiating_facility_id]
        ):
            return False

        if self.episode.get_case_property('enrolled_in_private') == 'true':
            return False

        return self.episode.get_case_property('episode_type') == 'confirmed_tb'

    @property
    @memoized
    def diagnosing_facility_id(self):
        """the owner_id of the person case at the time that the episode case with
        episode_type = 'confirmed_tb' was created (i.e., ignoring any changes of
        ownership that may have taken place since)

        """

        date_of_change = self.get_date_case_property_changed(
            'current_episode_type', 'confirmed_tb', case_type='person'
        )
        return self.get_owner_id_at_date(date_of_change)

    @property
    @memoized
    def treatment_initiating_facility_id(self):
        """the owner_id of the person case at the time that the Treatment Card is
        filled (i.e. when 'episode.episode_pending_registration' gets set to 'no')

        """
        if self.episode.get_case_property('treatment_initiated') not in ('yes_phi', 'yes_private'):
            return None

        date_of_change = self.get_date_case_property_changed('episode_pending_registration', 'no')
        return self.get_owner_id_at_date(date_of_change)

    def get_date_case_property_changed(self, case_property, value, case_type="episode"):
        """Returns the date a particular case property was changed to a specific value
        """
        date_of_change = None
        actions = self._episode_actions() if case_type == 'episode' else self._person_actions()
        for i, transactions in enumerate(actions):
            property_changed_info = self._property_changed_in_action(transactions, case_property)
            if property_changed_info and property_changed_info.new_value == value:
                # get the date that case_property changed
                date_of_change = parse_datetime(property_changed_info.modified_on)
                break

        return date_of_change

    @memoized
    def get_owner_id_at_date(self, date):
        """Returns the owner_id of the person case at the specified date
        """
        if date is None:
            return None

        for transaction in reversed(self._person_actions()):
            # go backwards in time, and find the first changed owner_id of the person case
            owner_id = self._get_owner_id_from_transaction(transaction, self.person.case_id)
            if owner_id and parse_datetime(owner_id.modified_on) <= date:
                return owner_id.new_value

    def _property_changed_in_action(self, action, case_property):
        if action.form is None:
            return False
        update_actions = [
            (update.modified_on_str, update.get_update_action())
            for update in get_case_updates(action.form)
        ]
        for (modified_on, action) in update_actions:
            if action:
                property_changed = action.dynamic_properties.get(case_property)
                if property_changed:
                    return PropertyChangedInfo(property_changed, modified_on)
        return False

    def _get_owner_id_from_transaction(self, transaction, case_id):
        if transaction.form is None:
            return None
        case_updates = get_case_updates(transaction.form)
        update_actions = [
            (update.modified_on_str, update.get_update_action()) for update in case_updates
            if update.id == case_id
        ]
        create_actions = [
            (update.modified_on_str, update.get_create_action()) for update in case_updates
            if update.id == case_id
        ]
        all_actions = update_actions + create_actions  # look through updates first, as these trump creates
        for modified_on, action in all_actions:
            if action:
                owner_id = action.get_known_properties().get('owner_id')
                if owner_id:
                    return PropertyChangedInfo(owner_id, modified_on)
        return None
