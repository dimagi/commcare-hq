DROP FUNCTION IF EXISTS get_ledger_values_for_cases(TEXT[]);

CREATE FUNCTION get_ledger_values_for_cases(p_case_ids TEXT[]) RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT p_case_ids;
    RUN ON hash_string(p_case_ids, 'siphash24');
$$ LANGUAGE plproxy;
