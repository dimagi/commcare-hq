DROP FUNCTION IF EXISTS save_case_and_related_models(
    TEXT,
    form_processor_commcarecasesql,
    form_processor_casetransaction[],
    form_processor_commcarecaseindexsql[],
    form_processor_caseattachmentsql[],
    INTEGER[],
    INTEGER[]
);

CREATE FUNCTION save_case_and_related_models(
    p_case_id TEXT,
    commcarecase form_processor_commcarecasesql,
    transactions form_processor_casetransaction[],
    indices form_processor_commcarecaseindexsql[],
    attachments form_processor_caseattachmentsql[],
    indices_to_delete INTEGER[],
    attachements_to_delete INTEGER[],
    case_pk OUT INTEGER
) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON hash_string(p_case_id, 'siphash24');
$$ LANGUAGE plproxy;
