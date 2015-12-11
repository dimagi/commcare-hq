DROP FUNCTION IF EXISTS check_form_exists(TEXT, TEXT);

CREATE FUNCTION check_form_exists(form_id TEXT, domain_name TEXT DEFAULT NULL, form_exists OUT BOOLEAN) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
