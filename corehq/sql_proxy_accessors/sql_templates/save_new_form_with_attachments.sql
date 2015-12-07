DROP FUNCTION IF EXISTS save_new_form_with_attachments(form_processor_xforminstancesql, form_processor_xformattachmentsql[]);

CREATE FUNCTION save_new_form_with_attachments(
    form form_processor_xforminstancesql,
    attachments form_processor_xformattachmentsql[],
    form_pk OUT INTEGER
) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form.form_id, 'siphash24');
$$ LANGUAGE plproxy;
