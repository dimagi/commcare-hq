DROP FUNCTION IF EXISTS update_form_problem_and_state(TEXT, TEXT, INTEGER);

CREATE FUNCTION update_form_problem_and_state(
    p_form_id TEXT, updated_problem TEXT, update_state INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET
        problem = updated_problem,
        state = update_state
    WHERE form_id = p_form_id;
END $$
LANGUAGE 'plpgsql';
