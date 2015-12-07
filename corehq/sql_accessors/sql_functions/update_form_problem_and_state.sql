DROP FUNCTION IF EXISTS update_form_problem_and_state(text, text, INTEGER);

CREATE FUNCTION update_form_problem_and_state(
    p_form_id text, updated_problem text, update_state INTEGER
) RETURNS VOID AS $$
BEGIN
    UPDATE form_processor_xforminstancesql SET
        problem = updated_problem,
        state = update_state
    WHERE form_id = p_form_id;
END $$
LANGUAGE 'plpgsql';
