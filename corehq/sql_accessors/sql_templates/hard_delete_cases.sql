DROP FUNCTION IF EXISTS hard_delete_cases(text, text[]);

CREATE FUNCTION hard_delete_cases(domain_name text, case_ids text[], deleted_count OUT int) AS $$
DECLARE
    verified_case_ids text[];
BEGIN
    -- remove any case_ids that aren't in the specified domain
    verified_case_ids := array(
        SELECT case_id from form_processor_commcarecasesql
        WHERE
            form_processor_commcarecasesql.case_id = ANY($2)
            AND form_processor_commcarecasesql.domain = $1
    );
    DELETE FROM form_processor_casetransaction WHERE form_processor_casetransaction.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_commcarecaseindexsql WHERE form_processor_commcarecaseindexsql.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_caseattachmentsql WHERE form_processor_caseattachmentsql.case_id = ANY(verified_case_ids);
    DELETE FROM form_processor_commcarecasesql WHERE form_processor_commcarecasesql.case_id = ANY(verified_case_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
