from django.conf import settings

ManageHostedCCZ_urlname = "manage_hosted_ccz"
ManageHostedCCZLink_urlname = "manage_hosted_ccz_links"
SMSUsageReport_urlname = 'sms_usage_report'
LocationReassignmentDownloadOnlyView_urlname = 'location_reassignment_download_only'
LocationReassignmentView_urlname = 'location_reassignment'
ICDS_DOMAIN = 'icds-cas'
IS_ICDS_ENVIRONMENT = settings.SERVER_ENVIRONMENT in settings.ICDS_ENVS
