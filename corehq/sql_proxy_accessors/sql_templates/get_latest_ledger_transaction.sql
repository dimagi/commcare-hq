DROP FUNCTION IF EXISTS get_latest_ledger_transaction(TEXT, TEXT, TEXT);

CREATE FUNCTION get_latest_ledger_transaction(
    p_case_id TEXT, p_section_id TEXT, p_entry_id TEXT
) RETURNS SETOF form_processor_ledgertransaction AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
