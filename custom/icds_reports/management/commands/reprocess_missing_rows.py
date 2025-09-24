from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.change_feed.data_sources import get_document_store_for_doc_type
from dimagi.utils.chunked import chunked


def reprocess_missing_rows(configs, check_only_nulls=False):
    domain = 'icds-cas'
    for config_id in configs:
        config, _ = get_datasource_config(config_id, domain)
        adapter = get_indicator_adapter(config)
        doc_ids = [r.doc_id for r in adapter.get_query_object().filter_by(supervisor_id=None)]
        if check_only_nulls:
            print(config_id, len(doc_ids))
            continue
        print("processing ", config_id, len(doc_ids))
        doc_store = get_document_store_for_doc_type(domain, config.referenced_doc_type)
        for chunked_ids in chunked(doc_ids, 50):
            try:
                docs = list(doc_store.iter_documents(chunked_ids))
                adapter.bulk_save(docs)
            except Exception as e:
                print("error processing for ", config_id, chunked_ids)
                print(e)
                print("trying serially")
                try:
                    for doc_id in doc_ids:
                        adapter.best_effort_save(doc_store.get_document(doc_id))
                except Exception as e:
                    print("error in serial processing doc", doc_id)

        print(len([r.doc_id for r in adapter.get_query_object().filter_by(supervisor_id=None)]),)
        print("finished processing ", config_id)
