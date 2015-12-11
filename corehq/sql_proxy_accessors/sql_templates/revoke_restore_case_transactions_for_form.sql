DROP FUNCTION IF EXISTS revoke_restore_case_transactions_for_form(TEXT[], TEXT, BOOLEAN);

CREATE FUNCTION revoke_restore_case_transactions_for_form(case_ids TEXT[], form_id TEXT, revoke BOOLEAN) RETURNS SETOF INTEGER AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;
