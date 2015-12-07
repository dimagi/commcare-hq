DROP FUNCTION IF EXISTS deprecate_form(TEXT, TEXT, TIMESTAMP);

-- TODO: can't do this the we're doing it now
CREATE FUNCTION deprecate_form(new_form_id TEXT, orig_id TEXT, edited_on TIMESTAMP) RETURNS VOID AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(orig_id, 'siphash24');
$$ LANGUAGE plproxy;
