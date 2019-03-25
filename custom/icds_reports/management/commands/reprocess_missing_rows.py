from corehq.apps.userreports.models import get_datasource_config, DataSourceConfiguration
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from dimagi.utils.chunked import chunked


def reprodcess_missing_rows(check_only_nulls=False):
    configs = [
        "static-icds-cas-static-complementary_feeding_forms",
        "static-icds-cas-static-dashboard_delivery_forms",
        "static-icds-cas-static-dashboard_birth_prepared",
    ]
    domain = 'icds-cas'
    for config_id in configs:
        config, _ = get_datasource_config(config_id, domain)
        adapter = get_indicator_adapter(config)
        if check_only_nulls:
            print "config_id", adapter.get_query_object().filter_by(supervisor_id=None).count()
            continue
        doc_ids = [r.doc_id for r in adapter.get_query_object().filter_by(supervisor_id=None)]
        print "processing ", config_id, len(doc_ids)
        doc_store = get_document_store_for_doc_type(domain, config.referenced_doc_type)
        for chunked_ids in chunked(doc_ids, 50):
            docs = list(doc_store.iter_documents(chunked_ids))
            adapter.bulk_save(docs)
