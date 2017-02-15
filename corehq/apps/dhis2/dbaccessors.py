from corehq.util.quickcache import quickcache


@quickcache(['domain'])
def get_dhis2_connection(domain_name):
    from corehq.apps.dhis2.models import Dhis2Connection

    result = Dhis2Connection.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'Dhis2Connection', None],
        include_docs=True,
        reduce=False,
    ).first()
    return Dhis2Connection.wrap(result['doc']) if result else None
