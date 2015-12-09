DROP FUNCTION IF EXISTS archive_unarchive_form(TEXT, TEXT, BOOLEAN);

CREATE FUNCTION archive_unarchive_form(form_id TEXT, archiving_user_id TEXT, archive BOOLEAN) RETURNS VOID AS $$
DECLARE
    new_state INT;
    operation TEXT;
    curtime TIMESTAMP := clock_timestamp() AT TIME ZONE 'utc';
BEGIN
    IF $3 THEN
        new_state := {{ FORM_STATE_ARCHIVED }};
        operation := '{{ FORM_OPERATION_ARCHIVE }}';
    ELSE
        new_state := {{ FORM_STATE_NORMAL }};
        operation := '{{ FORM_OPERATION_UNARCHIVE }}';
    END IF;

    INSERT INTO form_processor_xformoperationsql (form_id, user_id, operation, date)
            VALUES ($1, $2, operation, curtime);
    UPDATE form_processor_xforminstancesql SET state=new_state WHERE form_processor_xforminstancesql.form_id = $1;
END;
$$ LANGUAGE plpgsql;
