DROP FUNCTION IF EXISTS save_ledger_values(TEXT[], form_processor_ledgervalue[]);

CREATE FUNCTION save_ledger_values(case_ids TEXT[], ledger_values form_processor_ledgervalue[]) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids, ledger_values;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
