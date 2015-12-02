DROP FUNCTION IF EXISTS deprecate_form(TEXT, TEXT, TIMESTAMP);

CREATE FUNCTION deprecate_form(form_id TEXT, orig_id TEXT, edited_on TIMESTAMP) RETURNS VOID AS $$
DECLARE
    deprecated_state INT := 2;
BEGIN
    -- deprecate form
    UPDATE form_processor_xforminstancesql SET
        form_id = $1,
        orig_id = $2,
        edited_on = $3,
        state = deprecated_state
    WHERE
        form_processor_xforminstancesql.form_id = $2;

    -- update attachments
    UPDATE form_processor_xformattachmentsql SET
        form_id = $1
    WHERE
        form_processor_xformattachmentsql.form_id = $2;

    -- update operations
    UPDATE form_processor_xformoperationsql SET
        form_id = $1
    WHERE
        form_processor_xformoperationsql.form_id = $2;
END
$$
LANGUAGE 'plpgsql';
