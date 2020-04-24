from corehq.util.quickcache import quickcache


@quickcache(['domain_name'])
def get_dataset_maps(domain_name):
    from corehq.motech.dhis2.models import DataSetMap

    results = DataSetMap.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'DataSetMap', None],
        include_docs=True,
        reduce=False,
    ).all()
    return [DataSetMap.wrap(result['doc']) for result in results]
