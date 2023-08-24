DROP FUNCTION IF EXISTS get_form_ids_for_user_2(TEXT, TEXT, BOOLEAN);

CREATE FUNCTION get_form_ids_for_user_2(domain TEXT, user_id TEXT, is_deleted BOOLEAN) RETURNS TABLE (form_id VARCHAR(255)) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;
