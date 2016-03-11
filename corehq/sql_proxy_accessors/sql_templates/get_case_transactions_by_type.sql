DROP FUNCTION IF EXISTS get_case_transactions_by_type(TEXT, INTEGER);

CREATE FUNCTION get_case_transactions_by_type(case_id TEXT, transaction_type INTEGER) RETURNS SETOF form_processor_casetransaction AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;

