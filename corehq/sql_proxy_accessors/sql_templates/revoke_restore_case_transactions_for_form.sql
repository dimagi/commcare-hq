DROP FUNCTION IF EXISTS revoke_restore_case_transactions_for_form(TEXT, BOOLEAN);

CREATE FUNCTION revoke_restore_case_transactions_for_form(form_id TEXT, revoke BOOLEAN) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
