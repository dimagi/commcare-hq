DROP FUNCTION IF EXISTS update_form_state(TEXT, INTEGER);

CREATE FUNCTION update_form_state(
    p_form_id TEXT, update_state INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET
        state = update_state
    WHERE form_id = p_form_id;
END $$
LANGUAGE 'plpgsql';

