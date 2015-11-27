DROP FUNCTION IF EXISTS archive_form(text, text);

CREATE FUNCTION archive_form(form_id text, archiving_user_id text) AS $$
BEGIN
    INSERT INTO form_processor_xformoperationsql (form_id, user_id, operation, date)
        VALUES (form_id, archiving_user_id, 'archive', now() at time zone 'utc');

    UPDATE form_processor_xforminstancesql SET state=1 WHERE form_id = $1;
END;
$$ LANGUAGE plpgsql;
CaseTransaction.objects.filter(form_id=form_id).update(revoked=True)
