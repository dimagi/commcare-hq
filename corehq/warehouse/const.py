DJANGO_MAX_BATCH_SIZE = 1000

# Slugs

GROUP_STAGING_SLUG = 'group_staging'
USER_STAGING_SLUG = 'user_staging'
DOMAIN_STAGING_SLUG = 'domain_staging'
FORM_STAGING_SLUG = 'form_staging'
SYNCLOG_STAGING_SLUG = 'synclog_staging'
LOCATION_STAGING_SLUG = 'location_staging'
LOCATION_TYPE_STAGING_SLUG = 'location_type_staging'
APPLICATION_STAGING_SLUG = 'application_staging'

USER_DIM_SLUG = 'user_dim'
GROUP_DIM_SLUG = 'group_dim'
LOCATION_DIM_SLUG = 'location_dim'
DOMAIN_DIM_SLUG = 'domain_dim'
USER_LOCATION_DIM_SLUG = 'user_location_dim'
USER_GROUP_DIM_SLUG = 'user_group_dim'
APPLICATION_DIM_SLUG = 'application_dim'

APP_STATUS_FACT_SLUG = 'app_status_fact'
FORM_FACT_SLUG = 'form_fact'
SYNCLOG_FACT_SLUG = 'synclog_fact'

DIM_TABLES = [
    USER_DIM_SLUG,
    GROUP_DIM_SLUG,
    LOCATION_DIM_SLUG,
    DOMAIN_DIM_SLUG,
    USER_LOCATION_DIM_SLUG,
    USER_GROUP_DIM_SLUG,
    APPLICATION_DIM_SLUG,
]

FACT_TABLES = [
    APP_STATUS_FACT_SLUG,
    FORM_FACT_SLUG,
]

STAGING_TABLES = [
    GROUP_STAGING_SLUG,
    USER_STAGING_SLUG,
    DOMAIN_STAGING_SLUG,
    FORM_STAGING_SLUG,
    SYNCLOG_STAGING_SLUG,
    LOCATION_STAGING_SLUG,
    LOCATION_TYPE_STAGING_SLUG,
    APPLICATION_STAGING_SLUG,
]

ALL_TABLES = (
    DIM_TABLES +
    FACT_TABLES +
    STAGING_TABLES
)
