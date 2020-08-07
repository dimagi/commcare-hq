from corehq.sql_db.connections import get_db_alias_or_none, ICDS_UCR_CITUS_ENGINE_ID


def get_icds_ucr_citus_db_alias():
    return get_db_alias_or_none(ICDS_UCR_CITUS_ENGINE_ID)
