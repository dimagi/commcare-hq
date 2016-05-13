DROP FUNCTION IF EXISTS get_ledger_transactions_for_case(TEXT, TEXT, TEXT, TIMESTAMP, TIMESTAMP);

CREATE FUNCTION get_ledger_transactions_for_case(
    p_case_id TEXT,
    p_section_id TEXT DEFAULT NULL,
    p_entry_id TEXT DEFAULT NULL,
    date_window_start TIMESTAMP DEFAULT NULL,
    date_window_end TIMESTAMP DEFAULT NULL
) RETURNS SETOF form_processor_ledgertransaction AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
