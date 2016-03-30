DROP FUNCTION IF EXISTS get_ledger_value(TEXT, TEXT, TEXT);

CREATE FUNCTION get_ledger_value(p_case_id TEXT, p_section_id TEXT, p_entry_id TEXT) RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
