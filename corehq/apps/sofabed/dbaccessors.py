from sqlalchemy import Table, MetaData, Column, types, func, sql
from corehq.db import Session
from .models import FormData


# A SQLAlchemy representation of the FormData table.
# This skips the SQLAlchemy ORM and uses their SQL Expression Language
# http://docs.sqlalchemy.org/en/rel_0_8/core/tutorial.html#selecting
SAFormData = Table(
    FormData._meta.db_table,
    MetaData(),
    Column('domain', types.String),
    Column('received_on', types.DateTime),
    Column('time_end', types.DateTime),
    Column('xmlns', types.String),
    Column('user_id', types.String),
    Column('app_id', types.String),
)


def get_form_counts_by_user_xmlns(domain, startdate, enddate, by_submission_time=True):
    # This kind of COUNT and GROUP BY query isn't possible with the Django ORM
    col = SAFormData.columns
    date_field = col.received_on if by_submission_time else col.time_end
    query = (sql.select([func.count(), col.xmlns, col.user_id, col.app_id])
             .where(col.domain == domain)
             .where(startdate <= date_field)
             .where(date_field < enddate)
             .group_by(col.xmlns, col.user_id, col.app_id))
    return {
        (user_id, xmlns, app_id): count
        for count, xmlns, user_id, app_id in Session.execute(query)
    }
