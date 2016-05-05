DROP FUNCTION IF EXISTS delete_ledger_values(TEXT, TEXT, TEXT);

CREATE FUNCTION delete_ledger_values(
    p_case_id TEXT,
    p_section_id TEXT DEFAULT NULL,
    p_entry_id TEXT DEFAULT NULL) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
