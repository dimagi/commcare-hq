DROP FUNCTION IF EXISTS delete_ledger_transactions_for_form(TEXT[], TEXT);

CREATE FUNCTION delete_ledger_transactions_for_form(case_ids TEXT[], p_form_id TEXT, deleted_count OUT INTEGER) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
