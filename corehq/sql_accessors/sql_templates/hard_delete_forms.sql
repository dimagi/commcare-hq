DROP FUNCTION IF EXISTS hard_delete_forms(TEXT, TEXT[]);

CREATE FUNCTION hard_delete_forms(domain_name TEXT, form_ids TEXT[], deleted_count OUT INTEGER) AS $$
DECLARE
    verified_form_ids TEXT[];
BEGIN
    -- remove any form_ids that aren't in the specified domain
    verified_form_ids := array(
        SELECT form_id FROM form_processor_xforminstancesql
        WHERE
            form_processor_xforminstancesql.domain = domain_name
            AND form_processor_xforminstancesql.form_id = ANY(form_ids)
    );
    DELETE FROM form_processor_xformattachmentsql where form_id = ANY(verified_form_ids);
    DELETE FROM form_processor_xformoperationsql where form_id = ANY(verified_form_ids);
    DELETE FROM form_processor_xforminstancesql where form_id = ANY(verified_form_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
