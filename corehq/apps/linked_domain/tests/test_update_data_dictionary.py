from corehq.apps.data_dictionary.models import CaseType, CaseProperty

from corehq.apps.linked_domain.exceptions import UnsupportedActionError
from corehq.apps.linked_domain.local_accessors import get_data_dictionary
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.updates import update_data_dictionary

class TestUpdateDataDictionary(BaseLinkedAppsTest):
    def setUp(self):
        self.suspected = CaseType(domain=self.domain,
                                  name='Suspected',
                                  description='A suspected case',
                                  fully_generated=True)
        self.suspected.save()
        self.suspected_name = CaseProperty(case_type=self.suspected,
                                           name='Patient name',
                                           description='Name of patient',
                                           deprecated=False,
                                           data_type='plain',
                                           group='')
        self.suspected_name.save()
        self.suspected_date = CaseProperty(case_type=self.suspected,
                                           name='Date opened',
                                           description='Date the case was opened',
                                           deprecated=False,
                                           data_type='date',
                                           group='')
        self.suspected_date.save()

        self.confirmed = CaseType(domain=self.domain,
                                  name='Confirmed',
                                  description='A confirmed case',
                                  fully_generated=True)
        self.confirmed.save()
        self.confirmed_name = CaseProperty(case_type=self.confirmed,
                                           name='Patient name',
                                           description='Name of patient',
                                           deprecated=False,
                                           data_type='plain',
                                           group='')
        self.confirmed_name.save()
        self.confirmed_date = CaseProperty(case_type=self.confirmed,
                                           name='Date opened',
                                           description='Date the case was opened',
                                           deprecated=False,
                                           data_type='date',
                                           group='')
        self.confirmed_date.save()
        self.confirmed_test = CaseProperty(case_type=self.confirmed,
                                           name='Test',
                                           description='Type of test performed',
                                           deprecated=False,
                                           data_type='plain',
                                           group='')
        self.confirmed_test.save()
        

    def tearDown(self):
        self.suspected.delete()
        self.suspected_name.delete()
        # date field is deleted during test

        self.confirmed.delete()
        self.confirmed_name.delete()
        # date field is deleted during test
        self.confirmed_test.delete()


    def test_update_data_dictionary(self):
        self.assertEqual({}, get_data_dictionary(self.linked_domain))

        # Update linked domain
        update_data_dictionary(self.domain_link)

        # Linked domain should now have master domain's data dictionary
        linked_data_dictionary = get_data_dictionary(self.linked_domain)
        self.assertEqual(linked_data_dictionary, {
            'Suspected' : {
                'domain': self.linked_domain,
                'description' : 'A suspected case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Date opened': {
                        'description': 'Date the case was opened',
                        'deprecated': False,
                        'data_type': 'date',
                        'group': '',
                    }
                },
            },
            'Confirmed' : {
                'domain': self.linked_domain,
                'description' : 'A confirmed case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Date opened': {
                        'description': 'Date the case was opened',
                        'deprecated': False,
                        'data_type': 'date',
                        'group': '',
                    },
                    'Test': {
                        'description': 'Type of test performed',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    }
                }
            }
        })

        # Master domain's data dictionary should be untouched
        original_data_dictionary = get_data_dictionary(self.domain)
        self.assertEqual(original_data_dictionary, {
            'Suspected' : {
                'domain': self.domain,
                'description' : 'A suspected case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Date opened': {
                        'description': 'Date the case was opened',
                        'deprecated': False,
                        'data_type': 'date',
                        'group': '',
                    }
                }
            },
            'Confirmed' : {
                'domain': self.domain,
                'description' : 'A confirmed case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Date opened': {
                        'description': 'Date the case was opened',
                        'deprecated': False,
                        'data_type': 'date',
                        'group': '',
                    },
                    'Test': {
                        'description': 'Type of test performed',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    }
                }
            }
        })

        # Change the original domain and update the linked domain.
        self.suspected_date.delete()
        self.confirmed_date.delete()

        self.archived = CaseType(domain=self.domain,
                                 name='Archived',
                                 description='An archived case',
                                 fully_generated=True)
        self.archived.save()
        self.archived_name = CaseProperty(case_type=self.archived,
                                          name='Patient name',
                                          description='Name of patient',
                                          deprecated=False,
                                          data_type='plain',
                                          group='')
        self.archived_name.save()
        self.archived_reason = CaseProperty(case_type=self.archived,
                                            name='Reason',
                                            description='Reason for archiving',
                                            deprecated=False,
                                            data_type='plain',
                                            group='')
        self.archived_reason.save()
        update_data_dictionary(self.domain_link)

        # Checked that the linked domain has the new state.
        linked_data_dictionary = get_data_dictionary(self.linked_domain)
        self.assertEqual(linked_data_dictionary, {
            'Suspected' : {
                'domain': self.linked_domain,
                'description' : 'A suspected case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                },
            },
            'Confirmed' : {
                'domain': self.linked_domain,
                'description' : 'A confirmed case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Test': {
                        'description': 'Type of test performed',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    }
                }
            },
            'Archived' : {
                'domain': self.linked_domain,
                'description' : 'An archived case',
                'fully_generated' : True,
                'properties' : {
                    'Patient name': {
                        'description': 'Name of patient',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    },
                    'Reason': {
                        'description': 'Reason for archiving',
                        'deprecated': False,
                        'data_type': 'plain',
                        'group': '',
                    }
                }
            }
        })
        self.addCleanup(self.archived_name.delete)
        self.addCleanup(self.archived_reason.delete)
        self.addCleanup(self.archived.delete)
