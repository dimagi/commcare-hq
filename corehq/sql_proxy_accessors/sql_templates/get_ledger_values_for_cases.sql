DROP FUNCTION IF EXISTS get_ledger_values_for_cases(TEXT[], TEXT, TEXT, TIMESTAMP, TIMESTAMP);

CREATE FUNCTION get_ledger_values_for_cases(
    p_case_ids TEXT[],
    p_section_id TEXT DEFAULT NULL,
    p_entry_id TEXT DEFAULT NULL,
    date_window_start TIMESTAMP DEFAULT NULL,
    date_window_end TIMESTAMP DEFAULT NULL
) RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT p_case_ids;
    RUN ON hash_string(p_case_ids, 'siphash24');
$$ LANGUAGE plproxy;
