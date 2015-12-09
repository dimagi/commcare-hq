DROP FUNCTION IF EXISTS save_new_form_and_related_models(
    form_processor_xforminstancesql,
    form_processor_xformattachmentsql[],
    form_processor_xformoperationsql[]);

CREATE FUNCTION save_new_form_and_related_models(
    form form_processor_xforminstancesql,
    attachments form_processor_xformattachmentsql[],
    operations form_processor_xformoperationsql[],
    form_pk OUT INTEGER
) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(form.form_id, 'siphash24');
$$ LANGUAGE plproxy;
