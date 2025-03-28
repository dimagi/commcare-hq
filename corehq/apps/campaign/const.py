from django.utils.translation import gettext_noop

GAUGE_METRICS = (
    ('total_number_of_cases', gettext_noop('Total number of cases')),
    ('total_number_of_mobile_workers', gettext_noop('Total number of mobile workers')),
    ('total_number_of_active_mobile_workers', gettext_noop('Total number of active mobile workers')),
    ('total_number_of_inactive_web_users', gettext_noop('Total number of inactive web users')),
    ('total_number_of_forms_submitted_by_mobile_workers', gettext_noop(
        'Total number of forms submitted by mobile workers'))
)
