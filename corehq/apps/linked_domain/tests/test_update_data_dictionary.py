from corehq.apps.data_dictionary.models import CasePropertyGroup, CaseType, CaseProperty

from corehq.apps.linked_domain.local_accessors import get_data_dictionary
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest
from corehq.apps.linked_domain.updates import update_data_dictionary


class TestUpdateDataDictionary(BaseLinkedDomainTest):
    def setUp(self):
        self.suspected = CaseType(domain=self.domain,
                                  name='Suspected',
                                  description='A suspected case',
                                  fully_generated=True)
        self.suspected.save()
        self.suspected_group = CasePropertyGroup(case_type=self.suspected,
                                                 name='Suspected group',
                                                 description='Group of Suspected case properties')
        self.suspected_group.save()
        self.suspected_name = CaseProperty(case_type=self.suspected,
                                           name='Patient name',
                                           description='Name of patient',
                                           deprecated=False,
                                           data_type='plain',
                                           group=self.suspected_group)
        self.suspected_name.save()
        self.suspected_date = CaseProperty(case_type=self.suspected,
                                           name='Date opened',
                                           description='Date the case was opened',
                                           deprecated=False,
                                           data_type='date',
                                           group=self.suspected_group)
        self.suspected_date.save()

        self.confirmed = CaseType(domain=self.domain,
                                  name='Confirmed',
                                  description='A confirmed case',
                                  fully_generated=True)
        self.confirmed.save()
        self.confirmed_group = CasePropertyGroup(case_type=self.suspected,
                                                 name='Confirmed group',
                                                 description='Group of Confirmed case properties')
        self.confirmed_group.save()
        self.confirmed_name = CaseProperty(case_type=self.confirmed,
                                           name='Patient name',
                                           description='Name of patient',
                                           deprecated=False,
                                           data_type='plain',
                                           group=self.confirmed_group)
        self.confirmed_name.save()
        self.confirmed_date = CaseProperty(case_type=self.confirmed,
                                           name='Date opened',
                                           description='Date the case was opened',
                                           deprecated=False,
                                           data_type='date',
                                           group=self.confirmed_group)
        self.confirmed_date.save()
        self.confirmed_test = CaseProperty(case_type=self.confirmed,
                                           name='Test',
                                           description='Type of test performed',
                                           deprecated=False,
                                           data_type='plain',
                                           group=self.confirmed_group)
        self.confirmed_test.save()

    def tearDown(self):
        self.suspected.delete()
        self.confirmed.delete()

    def test_update_data_dictionary(self):
        self.assertEqual({}, get_data_dictionary(self.linked_domain))

        # Update linked domain
        update_data_dictionary(self.domain_link)

        # Linked domain should now have master domain's data dictionary
        linked_data_dictionary = get_data_dictionary(self.linked_domain)

        def expected_property_type(description, data_type):
            return {
                'description': description,
                'deprecated': False,
                'data_type': data_type,
            }

        def expected_group_type(description, index, properties):
            return {
                'description': description,
                'index': index,
                'properties': properties
            }

        patient_name_suspected = expected_property_type('Name of patient', 'plain')
        date_opened_suspected = expected_property_type('Date the case was opened', 'date')

        patient_name_confirmed = expected_property_type('Name of patient', 'plain')
        date_opened_confirmed = expected_property_type('Date the case was opened', 'date')
        test_performed = expected_property_type('Type of test performed', 'plain')

        suspected_properties = {'Patient name': patient_name_suspected,
                                'Date opened': date_opened_suspected}
        group_suspected_props = expected_group_type('Group of Suspected case properties', 0, suspected_properties)

        confirmed_properties = {'Patient name': patient_name_confirmed,
                                'Date opened': date_opened_confirmed,
                                'Test': test_performed}
        group_confirmed_props = expected_group_type('Group of Confirmed case properties', 0, confirmed_properties)

        def expected_case_type(domain, description, groups):
            return {
                'domain': domain,
                'description': description,
                'fully_generated': True,
                'is_deprecated': False,
                'groups': groups
            }

        self.assertEqual(linked_data_dictionary, {
            'Suspected': expected_case_type(self.linked_domain,
                                            'A suspected case',
                                            {"Suspected group": group_suspected_props}),
            'Confirmed': expected_case_type(self.linked_domain,
                                            'A confirmed case',
                                            {"Confirmed group": group_confirmed_props})
        })

        # Master domain's data dictionary should be untouched
        original_data_dictionary = get_data_dictionary(self.domain)
        self.assertEqual(original_data_dictionary, {
            'Suspected': expected_case_type(self.domain,
                                            'A suspected case',
                                            {"Suspected group": group_suspected_props}),
            'Confirmed': expected_case_type(self.domain,
                                            'A confirmed case',
                                            {"Confirmed group": group_confirmed_props})
        })

        # Change the original domain and update the linked domain.
        self.suspected_date.delete()
        del suspected_properties['Date opened']

        self.confirmed_date.delete()
        del confirmed_properties['Date opened']

        self.archived = CaseType(domain=self.domain,
                                 name='Archived',
                                 description='An archived case',
                                 fully_generated=True)
        self.archived.save()
        self.archived_group = CasePropertyGroup(case_type=self.suspected,
                                                name='Archived group',
                                                description='Group of Archived case properties')
        self.archived_group.save()
        self.archived_name = CaseProperty(case_type=self.archived,
                                          name='Patient name',
                                          description='Name of patient',
                                          deprecated=False,
                                          data_type='plain',
                                          group=self.archived_group)
        self.archived_name.save()
        self.archived_reason = CaseProperty(case_type=self.archived,
                                            name='Reason',
                                            description='Reason for archiving',
                                            deprecated=False,
                                            data_type='plain',
                                            group=self.archived_group)
        self.archived_reason.save()
        update_data_dictionary(self.domain_link)

        patient_name_archived = expected_property_type('Name of patient', 'plain')
        reason_archived = expected_property_type('Reason for archiving', 'plain')
        archived_properties = {'Patient name': patient_name_archived,
                            'Reason': reason_archived}
        group_archived_props = expected_group_type('Group of Archived case properties', 0, archived_properties)

        # Checked that the linked domain has the new state.
        linked_data_dictionary = get_data_dictionary(self.linked_domain)
        self.assertEqual(linked_data_dictionary, {
            'Suspected': expected_case_type(self.linked_domain,
                                            'A suspected case',
                                            {"Suspected group": group_suspected_props}),
            'Confirmed': expected_case_type(self.linked_domain,
                                            'A confirmed case',
                                            {"Confirmed group": group_confirmed_props}),
            'Archived': expected_case_type(self.linked_domain,
                                           'An archived case',
                                           {"Archived group": group_archived_props})
        })
        self.addCleanup(self.archived_name.delete)
        self.addCleanup(self.archived_reason.delete)
        self.addCleanup(self.archived.delete)
