DROP FUNCTION IF EXISTS get_case_transactions(text);

CREATE FUNCTION get_case_transactions(case_id text) RETURNS SETOF form_processor_casetransaction AS $$
    SELECT * FROM form_processor_casetransaction where case_id = $1 ORDER BY server_date;
$$ LANGUAGE SQL;
