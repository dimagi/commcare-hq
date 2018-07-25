DROP FUNCTION IF EXISTS compare_server_client_case_transaction_order(TEXT);

CREATE FUNCTION compare_server_client_case_transaction_order(
    _case_id TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        WITH transaction_orders AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY server_date) ordinal_by_server_date,
                ROW_NUMBER() OVER (ORDER BY client_date) ordinal_by_client_date
            FROM form_processor_casetransaction
            WHERE case_id = _case_id
        )
        SELECT NOT EXISTS (
            SELECT *
            FROM transaction_orders
            WHERE ordinal_by_server_date != ordinal_by_client_date
        )
    );
END;
$$ LANGUAGE plpgsql;
