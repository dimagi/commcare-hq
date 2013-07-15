DOMAIN_INDEX="hqdomains_b6e57e7b5a37d81efb426cc46ab1c3e7"
DOMAIN_MAPPING={'date_formats': ['yyyy-MM-dd', "yyyy-MM-dd'T'HH:mm:ssZZ", "yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'", "yyyy-MM-dd'T'HH:mm:ss'Z'", "yyyy-MM-dd'T'HH:mm:ssZ", "yyyy-MM-dd'T'HH:mm:ssZZ'Z'", "yyyy-MM-dd'T'HH:mm:ss.SSSZZ", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd' 'HH:mm:ss", "yyyy-MM-dd' 'HH:mm:ss.SSSSSS", "mm/dd/yy' 'HH:mm:ss"], 'dynamic': False, '_meta': {'comment': 'Autogenerated [corehq.apps.domain.models.Domain] mapping from ptop_generate_mapping 07/15/2013', 'created': None}, 'date_detection': False, 'properties': {'cda': {'dynamic': False, 'type': 'object', 'properties': {'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'user_id': {'type': 'string'}, 'signed': {'type': 'boolean'}, 'user_ip': {'type': 'string'}, 'date': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'type': {'index': 'not_analyzed', 'type': 'string'}}}, 'sub_area': {'type': 'string'}, 'cp_n_inactive_cases': {'type': 'long'}, 'cp_n_cases': {'type': 'long'}, 'cp_n_active_cases': {'type': 'long'}, 'default_sms_backend_id': {'type': 'string'}, 'sms_case_registration_owner_id': {'type': 'string'}, 'multimedia_included': {'type': 'boolean'}, 'phone_model': {'type': 'string'}, 'copy_history': {'type': 'string'}, 'title': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'title': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'image_type': {'type': 'string'}, 'description': {'type': 'string'}, 'name': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'name': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'cp_n_cc_users': {'type': 'long'}, 'is_snapshot': {'type': 'boolean'}, 'sms_case_registration_user_id': {'type': 'string'}, 'cp_n_web_users': {'type': 'long'}, 'is_shared': {'type': 'boolean'}, 'billing_address': {'dynamic': False, 'type': 'object', 'properties': {'state_province': {'type': 'string'}, 'city': {'type': 'string'}, 'name': {'type': 'string'}, 'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'country': {'type': 'string'}, 'postal_code': {'type': 'string'}}}, 'is_active': {'type': 'boolean'}, 'default_timezone': {'type': 'string'}, 'date_created': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'deployment': {'dynamic': False, 'type': 'object', 'properties': {'city': {'fields': {'city': {'index': 'analyzed', 'type': 'string'}, 'exact': {'index': 'not_analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'description': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'description': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'country': {'fields': {'country': {'index': 'analyzed', 'type': 'string'}, 'exact': {'index': 'not_analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'region': {'fields': {'region': {'index': 'analyzed', 'type': 'string'}, 'exact': {'index': 'not_analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'date': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'public': {'type': 'boolean'}}}, 'is_public': {'type': 'boolean'}, 'cp_n_60_day_cases': {'type': 'long'}, 'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'creating_user': {'type': 'string'}, 'is_sms_billable': {'type': 'boolean'}, 'case_display': {'dynamic': False, 'type': 'object', 'properties': {'doc_type': {'index': 'not_analyzed', 'type': 'string'}}}, 'yt_id': {'type': 'string'}, 'cp_n_active_cc_users': {'type': 'long'}, 'customer_type': {'type': 'string'}, 'case_sharing': {'type': 'boolean'}, 'currency_code': {'type': 'string'}, 'hr_name': {'type': 'string'}, 'cp_first_form': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'eula': {'dynamic': False, 'type': 'object', 'properties': {'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'user_id': {'type': 'string'}, 'signed': {'type': 'boolean'}, 'user_ip': {'type': 'string'}, 'date': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'type': {'type': 'string'}}}, 'project_type': {'type': 'string', 'analyzer': 'comma'}, 'restrict_superusers': {'type': 'boolean'}, 'is_test': {'type': 'boolean'}, 'cp_last_form': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'image_path': {'type': 'string'}, 'sms_case_registration_enabled': {'type': 'boolean'}, 'is_approved': {'type': 'boolean'}, 'author': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'author': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'migrations': {'dynamic': False, 'type': 'object', 'properties': {'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'has_migrated_permissions': {'type': 'boolean'}}}, 'internal': {'dynamic': False, 'type': 'object', 'properties': {'using_call_center': {'type': 'boolean'}, 'sf_contract_id': {'type': 'string'}, 'self_started': {'type': 'boolean'}, 'can_use_data': {'type': 'boolean'}, 'sub_area': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'sub_area': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'area': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'area': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'using_adm': {'type': 'boolean'}, 'notes': {'type': 'string'}, 'project_state': {'type': 'string'}, 'organization_name': {'type': 'string'}, 'commcare_edition': {'type': 'string'}, 'custom_eula': {'type': 'boolean'}, 'initiative': {'fields': {'exact': {'index': 'not_analyzed', 'type': 'string'}, 'initiative': {'index': 'analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'platform': {'type': 'string'}, 'services': {'type': 'string'}, 'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'sf_account_id': {'type': 'string'}}}, 'short_description': {'fields': {'short_description': {'index': 'analyzed', 'type': 'string'}, 'exact': {'index': 'not_analyzed', 'type': 'string'}}, 'type': 'multi_field'}, 'survey_management_enabled': {'type': 'boolean'}, 'snapshot_time': {'type': 'date', 'format': "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"}, 'tags': {'type': 'string'}, 'downloads': {'type': 'long'}, 'call_center_config': {'dynamic': False, 'type': 'object', 'properties': {'doc_type': {'index': 'not_analyzed', 'type': 'string'}, 'case_type': {'type': 'string'}, 'enabled': {'type': 'boolean'}, 'case_owner_id': {'type': 'string'}}}, 'cp_n_forms': {'type': 'long'}, 'cp_has_app': {'type': 'boolean'}, 'sms_mobile_worker_registration_enabled': {'type': 'boolean'}, 'sms_case_registration_type': {'type': 'string'}, 'publisher': {'type': 'string'}, 'license': {'type': 'string'}, 'billing_number': {'type': 'string'}, 'area': {'type': 'string'}, 'attribution_notes': {'type': 'string'}, 'commtrack_enabled': {'type': 'boolean'}, 'published': {'type': 'boolean'}, 'billable_client': {'type': 'string'}, 'organization': {'type': 'string'}, 'full_downloads': {'type': 'long'}, 'cp_is_active': {'type': 'boolean'}}}