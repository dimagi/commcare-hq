DROP FUNCTION IF EXISTS save_ledger_values(TEXT, form_processor_ledgervalue, form_processor_ledgertransaction[], TEXT);

CREATE FUNCTION save_ledger_values(
    case_id TEXT,
    ledger_value form_processor_ledgervalue,
    ledger_transactions form_processor_ledgertransaction[],
    deprecated_form_id TEXT DEFAULT NULL) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
