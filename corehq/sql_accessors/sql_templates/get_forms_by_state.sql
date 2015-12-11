DROP FUNCTION IF EXISTS get_forms_by_state(TEXT, INTEGER, INTEGER, BOOLEAN);

CREATE FUNCTION get_forms_by_state(
    domain_name TEXT,
    state INTEGER,
    limit_to INTEGER,
    recent_first BOOLEAN DEFAULT TRUE
    )
    RETURNS SETOF form_processor_xforminstancesql AS $$
DECLARE
    sort_dir TEXT;
BEGIN
    IF recent_first THEN
        sort_dir := 'DESC';
    ELSE
        sort_dir := 'ASC';
    END IF;
    RETURN QUERY EXECUTE format(
        'SELECT * FROM form_processor_xforminstancesql WHERE domain = $1 AND state = $2 ORDER BY received_on %s LIMIT %s',
        sort_dir, limit_to
        )
        USING domain_name, state;
END;
$$ LANGUAGE plpgsql;
