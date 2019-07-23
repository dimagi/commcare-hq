from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.elastic import es_index
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

from pillowtop.es_utils import ElasticsearchIndexInfo


USER_INDEX = es_index("hqusers_2017-09-07")
USER_MAPPING = {
 '_meta': {'created': None},
 'date_detection': False,
 'date_formats': DATE_FORMATS_ARR,
 'dynamic': False,
 'properties': {'CURRENT_VERSION': {'type': 'text'},
                'base_doc': {'type': 'text'},
                'created_on': {'format': DATE_FORMATS_STRING,
                               'type': 'date'},
                'date_joined': {'format': DATE_FORMATS_STRING,
                                'type': 'date'},
                'doc_type': {'type': 'keyword'},
                'domain': {'fields': {'domain': {'type': 'text'},
                                      'exact': {'type': 'keyword'}},
                           'type': 'text'},
                'user_location_id': {'type': 'keyword'},
                'location_id': {'type': 'keyword'},
                'assigned_location_ids': {"type": "text"},
                'phone_numbers': {"type": "text"},
                'domain_membership': {'dynamic': False,
                                      'properties': {'doc_type': {'type': 'keyword'},
                                                     'domain': {'fields': {'domain': {'type': 'text'},
                                                                           'exact': {'type': 'keyword'}},
                                                                'type': 'text'},
                                                     'is_admin': {'type': 'boolean'},
                                                     'override_global_tz': {'type': 'boolean'},
                                                     'role_id': {'type': 'text'},
                                                     'timezone': {'type': 'text'},
                                                     'location_id': {'type': 'keyword'}},
                                      'type': 'object'},
                'domain_memberships': {'dynamic': False,
                                      'properties': {'doc_type': {'type': 'keyword'},
                                                     'domain': {'fields': {'domain': {'type': 'text'},
                                                                           'exact': {'type': 'keyword'}},
                                                                'type': 'text'},
                                                     'is_admin': {'type': 'boolean'},
                                                     'override_global_tz': {'type': 'boolean'},
                                                     'role_id': {'type': 'text'},
                                                     'timezone': {'type': 'text'},
                                                     'location_id': {'type': 'keyword'}},
                                      'type': 'object'},
                'analytics_enabled': {'type': 'boolean'},
                'eulas': {'dynamic': False,
                          'properties': {'date': {'format': DATE_FORMATS_STRING,
                                                  'type': 'date'},
                                         'doc_type': {'type': 'keyword'},
                                         'signed': {'type': 'boolean'},
                                         'type': {'type': 'text'},
                                         'user_id': {'type': 'text'},
                                         'user_ip': {'type': 'text'},
                                         'version': {'type': 'text'}},
                          'type': 'object'},
                'first_name': {'type': 'text'},
                'is_active': {'type': 'boolean'},
                'is_staff': {'type': 'boolean'},
                'is_demo_user': {'type': 'boolean'},
                'is_superuser': {'type': 'boolean'},
                'language': {'type': 'text'},
                'last_login': {'format': DATE_FORMATS_STRING,
                               'type': 'date'},
                'last_name': {'type': 'text'},
                'password': {'type': 'text'},
                'registering_device_id': {'type': 'text'},
                'reporting_metadata': {'dynamic': False,
                                       'properties': {
                                           'last_submissions': {
                                               'dynamic': False,
                                               'properties': {
                                                   'submission_date': {'format': DATE_FORMATS_STRING,
                                                                       'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_id': {'type': 'text'},
                                                   'device_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                                   'commcare_version': {'type': 'text'},
                                               },
                                               'type': 'nested'
                                           },
                                           'last_submission_for_user': {
                                               'dynamic': False,
                                               'properties': {
                                                   'submission_date': {'format': DATE_FORMATS_STRING,
                                                                       'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_id': {'type': 'text'},
                                                   'device_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                                   'commcare_version': {'type': 'text'},
                                               },
                                               'type': 'object'
                                           },
                                           'last_syncs': {
                                               'dynamic': False,
                                               'properties': {
                                                   'sync_date': {'format': DATE_FORMATS_STRING,
                                                                 'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                               },
                                               'type': 'nested'
                                           },
                                           'last_sync_for_user': {
                                               'dynamic': False,
                                               'properties': {
                                                   'sync_date': {'format': DATE_FORMATS_STRING,
                                                                 'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                               },
                                               'type': 'object'
                                           },
                                           'last_builds': {
                                               'dynamic': False,
                                               'properties': {
                                                   'build_version_date': {'format': DATE_FORMATS_STRING,
                                                                          'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                               },
                                               'type': 'nested'
                                           },
                                           'last_build_for_user': {
                                               'dynamic': False,
                                               'properties': {
                                                   'build_version_date': {'format': DATE_FORMATS_STRING,
                                                                          'type': 'date'},
                                                   'app_id': {'type': 'text'},
                                                   'build_version': {'type': 'integer'},
                                               },
                                               'type': 'object'
                                           },
                                       },
                                       'type': 'object'},
                'devices': {
                    'dynamic': False,
                    'type': 'nested',
                    'properties': {
                        'device_id': {'type': 'keyword'},
                        'last_used': {'type': 'date', 'format': DATE_FORMATS_STRING},
                        'commcare_version': {'type': 'text'},
                        'app_meta': {
                            'dynamic': False,
                            'type': 'nested',
                            'properties': {
                                'app_id': {'type': 'keyword'},
                                'build_id': {'type': 'keyword'},
                                'build_version': {'type': 'integer'},
                                'last_request': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_submission': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_sync': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_heartbeat': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'num_unsent_forms': {'type': 'integer'},
                                'num_quarantined_forms': {'type': 'integer'},
                            }
                        },
                    }
                },
                'last_device': {
                    'dynamic': False,
                    'type': 'object',
                    'properties': {
                        'device_id': {'type': 'keyword'},
                        'last_used': {'type': 'date', 'format': DATE_FORMATS_STRING},
                        'commcare_version': {'type': 'text'},
                        'app_meta': {
                            'dynamic': False,
                            'type': 'object',
                            'properties': {
                                'app_id': {'type': 'keyword'},
                                'build_id': {'type': 'keyword'},
                                'build_version': {'type': 'integer'},
                                'last_request': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_submission': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_sync': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'last_heartbeat': {'type': 'date', 'format': DATE_FORMATS_STRING},
                                'num_unsent_forms': {'type': 'integer'},
                                'num_quarantined_forms': {'type': 'integer'},
                            }
                        },
                    }
                },
                'status': {'type': 'text'},
                'user_data': {'type': 'object', 'enabled': False},
                'user_data_es': {
                    'type': 'nested',
                    'dynamic': False,
                    'properties': {
                        'key': {
                            'type': 'keyword'
                        },
                        'value': {
                            'type': 'text'
                        }
                    }
                },
                'base_username': {'fields': {'base_username': {'type': 'text'},
                                             'exact': {'type': 'keyword'}},
                                 'type': 'text'},
                'username': {'fields': {'exact': {'type': 'keyword'},
                                        'username': {'analyzer': 'standard',
                                                     'type': 'text'}},
                             'type': 'text'},
                '__group_ids': {'type': 'text'},
                '__group_names': {'fields': {'__group_names': {'type': 'text'},
                                             'exact': { 'type': 'keyword'}},
                                  'type': 'text'}}}

USER_INDEX_INFO = ElasticsearchIndexInfo(
    index=USER_INDEX,
    alias='hqusers',
    type='user',
    mapping=USER_MAPPING,
)
