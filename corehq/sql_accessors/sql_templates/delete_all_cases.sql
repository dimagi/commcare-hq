DROP FUNCTION IF EXISTS delete_all_cases(TEXT);

-- has to return SETOF for plproxy
CREATE FUNCTION delete_all_cases(domain_name TEXT) RETURNS SETOF INTEGER AS $$
DECLARE
    query_expr    TEXT := 'SELECT case_id FROM form_processor_commcarecasesql';
    domain_filter      TEXT := ' domain = $1';
    case_ids           TEXT[];
BEGIN
    IF $1 <> '' THEN
        query_expr := query_expr || ' WHERE' || domain_filter;
    END IF;

    EXECUTE format('SELECT ARRAY(%s)', query_expr)
        INTO case_ids
        USING domain_name;

    DELETE FROM form_processor_casetransaction WHERE form_processor_casetransaction.case_id = ANY(case_ids);
    DELETE FROM form_processor_commcarecaseindexsql WHERE form_processor_commcarecaseindexsql.case_id = ANY(case_ids);
    DELETE FROM form_processor_caseattachmentsql WHERE form_processor_caseattachmentsql.case_id = ANY(case_ids);
    DELETE FROM form_processor_commcarecasesql WHERE form_processor_commcarecasesql.case_id = ANY(case_ids);
END;
$$ LANGUAGE plpgsql;
