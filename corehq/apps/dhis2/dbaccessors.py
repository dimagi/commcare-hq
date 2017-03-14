from corehq.util.quickcache import quickcache


@quickcache(['domain_name'])
def get_dhis2_connection(domain_name):
    from corehq.apps.dhis2.models import Dhis2Connection

    result = Dhis2Connection.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'Dhis2Connection', None],
        include_docs=True,
        reduce=False,
    ).first()
    return Dhis2Connection.wrap(result['doc']) if result else None


@quickcache(['domain_name'])
def get_dataset_maps(domain_name):
    from corehq.apps.dhis2.models import DataSetMap

    results = DataSetMap.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'DataSetMap', None],
        include_docs=True,
        reduce=False,
    ).all()
    return [DataSetMap.wrap(result['doc']) for result in results]


@quickcache(['domain_name'])
def get_dhis2_logs(domain_name):
    from corehq.apps.dhis2.models import Dhis2Log

    results = Dhis2Log.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'Dhis2Log', None],
        include_docs=True,
        reduce=False,
    ).all()
    return [Dhis2Log.wrap(result['doc']) for result in results]
