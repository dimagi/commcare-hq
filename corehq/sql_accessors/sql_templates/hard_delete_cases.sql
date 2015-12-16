DROP FUNCTION IF EXISTS hard_delete_cases(TEXT, TEXT[]);

CREATE FUNCTION hard_delete_cases(domain_name TEXT, case_ids TEXT[], deleted_count OUT INTEGER) AS $$
DECLARE
    verified_case_ids TEXT[];
BEGIN
    -- remove any case_ids that aren't in the specified domain
    verified_case_ids := array(
        SELECT case_id from form_processor_commcarecasesql
        WHERE
            form_processor_commcarecasesql.case_id = ANY(case_ids)
            AND form_processor_commcarecasesql.domain = domain_name
    );
    DELETE FROM form_processor_casetransaction WHERE form_processor_casetransaction.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_commcarecaseindexsql WHERE form_processor_commcarecaseindexsql.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_caseattachmentsql WHERE form_processor_caseattachmentsql.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_commcarecasesql WHERE form_processor_commcarecasesql.case_id = ANY(verified_case_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
