DROP FUNCTION IF EXISTS get_case_by_location_id(TEXT, TEXT);

CREATE FUNCTION get_case_by_location_id(domain_name TEXT, p_location_id TEXT) RETURNS SETOF form_processor_commcarecasesql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM form_processor_commcarecasesql
    WHERE domain = domain_name AND location_id = p_location_id AND type = 'supply-point';
END;
$$ LANGUAGE plpgsql;
