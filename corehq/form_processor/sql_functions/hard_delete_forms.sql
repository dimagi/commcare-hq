DROP FUNCTION IF EXISTS hard_delete_forms(text, text[]);

CREATE FUNCTION hard_delete_forms(domain_name text, form_ids text[], deleted_count OUT int) AS $$
DECLARE
    verified_form_ids text[];
BEGIN
    -- remove any form_ids that aren't in the specified domain
    verified_form_ids := array(
        SELECT form_id FROM form_processor_xforminstancesql
        WHERE
            form_processor_xforminstancesql.domain = $1
            AND form_processor_xforminstancesql.form_id = ANY($2)
    );
    DELETE FROM form_processor_xformattachmentsql where form_id = ANY(verified_form_ids);
    DELETE FROM form_processor_xformoperationsql where form_id = ANY(verified_form_ids);
    DELETE FROM form_processor_xforminstancesql where form_id = ANY(verified_form_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
