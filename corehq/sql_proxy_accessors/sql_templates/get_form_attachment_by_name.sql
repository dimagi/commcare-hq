DROP FUNCTION IF EXISTS get_form_attachment_by_name(TEXT, TEXT);

CREATE FUNCTION get_form_attachment_by_name(form_id TEXT, name TEXT) RETURNS SETOF form_processor_xformattachmentsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form_id, 'siphash24');
$$ LANGUAGE plproxy;
