DROP FUNCTION IF EXISTS get_case_attachment_by_identifier(TEXT, TEXT);

CREATE FUNCTION get_case_attachment_by_identifier(case_id TEXT, name TEXT) RETURNS SETOF form_processor_caseattachmentsql AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(case_id, 'siphash24');
$$ LANGUAGE plproxy;
