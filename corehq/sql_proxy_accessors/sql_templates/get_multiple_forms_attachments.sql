DROP FUNCTION IF EXISTS get_mulitple_forms_attachments(TEXT[]);

CREATE FUNCTION get_mulitple_forms_attachments(form_ids TEXT[]) RETURNS SETOF form_processor_xformattachmentsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT form_ids;
    RUN ON hash_string(form_ids, 'siphash24');
$$ LANGUAGE plproxy;
