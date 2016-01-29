DROP FUNCTION IF EXISTS update_form_state(TEXT, INTEGER);

CREATE FUNCTION update_form_problem_and_state(form_id TEXT, update_state INTEGER) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
