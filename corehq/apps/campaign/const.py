from django.utils.translation import gettext_noop

GAUGE_METRICS = (
    ('number_of_cases', gettext_noop('Number of cases')),
    ('number_of_mobile_workers', gettext_noop('Number of mobile workers')),
    ('number_of_active_mobile_workers', gettext_noop('Number of active mobile workers')),
    ('number_of_inactive_web_users', gettext_noop('Number of inactive web users')),
    ('number_of_forms_submitted_by_mobile_workers', gettext_noop('Number of forms submitted by mobile workers'))
)
