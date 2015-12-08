DROP FUNCTION IF EXISTS get_forms_by_state(text, integer, integer, boolean);

CREATE FUNCTION get_forms_by_state(
    domain_name text,
    state integer,
    limit_to integer,
    recent_first boolean default TRUE
    )
    RETURNS SETOF form_processor_xforminstancesql AS $$
DECLARE
    sort_dir text;
BEGIN
    IF $4 THEN
        sort_dir := 'DESC';
    ELSE
        sort_dir := 'ASC';
    END IF;
    RETURN QUERY EXECUTE format(
        'SELECT * FROM form_processor_xforminstancesql WHERE domain = $1 AND state = $2 ORDER BY received_on %s LIMIT %s',
        sort_dir, $3
        )
        USING $1, $2;
END;
$$ LANGUAGE plpgsql;
