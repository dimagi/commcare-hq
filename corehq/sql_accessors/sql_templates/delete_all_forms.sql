DROP FUNCTION IF EXISTS delete_all_forms(TEXT, TEXT);

-- has to return SETOF for plproxy
CREATE FUNCTION delete_all_forms(domain_name TEXT, form_user_id TEXT) RETURNS SETOF INTEGER AS $$
DECLARE
    query_expr    TEXT := 'SELECT form_id FROM form_processor_xforminstancesql';
    domain_filter      TEXT := ' domain = $1';
    type_filter        TEXT := ' user_id = $2';
    form_ids           TEXT[];
BEGIN
    IF $1 <> '' THEN
        query_expr := query_expr || ' WHERE' || domain_filter;
    END IF;

    IF $2 <> '' THEN
        IF $1 <> '' THEN
            query_expr := query_expr || ' AND' || type_filter;
        ELSE
            query_expr := query_expr || ' WHERE' || type_filter;
        END IF;
    END IF;

    EXECUTE format('SELECT ARRAY(%s)', query_expr)
        INTO form_ids
        USING domain_name, form_user_id;

    DELETE FROM form_processor_xformattachmentsql where form_id = ANY(form_ids);
    DELETE FROM form_processor_xformoperationsql where form_id = ANY(form_ids);
    DELETE FROM form_processor_xforminstancesql where form_id = ANY(form_ids);
END;
$$ LANGUAGE plpgsql;
