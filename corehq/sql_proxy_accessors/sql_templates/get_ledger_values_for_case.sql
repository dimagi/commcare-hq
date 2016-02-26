DROP FUNCTION IF EXISTS get_ledger_values_for_case(TEXT);

CREATE FUNCTION get_ledger_values_for_case(p_case_id TEXT) RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
