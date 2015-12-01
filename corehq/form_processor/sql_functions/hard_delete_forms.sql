DROP FUNCTION IF EXISTS hard_delete_forms(form_id text);

CREATE FUNCTION hard_delete_forms(form_ids text[], deleted_count OUT int) AS $$
BEGIN
    DELETE FROM form_processor_xformattachmentsql where form_id = ANY($1);
    DELETE FROM form_processor_xformoperationsql where form_id = ANY($1);
    DELETE FROM form_processor_xforminstancesql where form_id = ANY($1);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
END;
$$ LANGUAGE plpgsql;
