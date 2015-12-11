DROP FUNCTION IF EXISTS archive_unarchive_form(TEXT, TEXT, BOOLEAN);

CREATE FUNCTION archive_unarchive_form(form_id TEXT, archiving_user_id TEXT, archive BOOLEAN) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
