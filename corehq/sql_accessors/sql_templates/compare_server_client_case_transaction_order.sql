DROP FUNCTION IF EXISTS compare_server_client_case_transaction_order(TEXT, INTEGER);

CREATE FUNCTION compare_server_client_case_transaction_order(
    _case_id TEXT,
    rebuild_types INTEGER
) RETURNS BOOLEAN AS $$

BEGIN
    RETURN (
        WITH most_recent_rebuild_date AS (
            SELECT server_date AS rebuild_date
            FROM form_processor_casetransaction
            WHERE
                type & rebuild_types != 0
                AND case_id = _case_id
            ORDER BY server_date DESC
            LIMIT 1
        ),

        transaction_orders AS (
            SELECT ROW_NUMBER() OVER (ORDER BY server_date) ordinal_by_server_date,
                   ROW_NUMBER() OVER (ORDER BY client_date) ordinal_by_client_date
            FROM form_processor_casetransaction, most_recent_rebuild_date
            WHERE case_id = _case_id
                  AND server_date IS NOT NULL
                  AND client_date IS NOT NULL
                  AND server_date >= rebuild_date
        )

        SELECT NOT EXISTS (
            SELECT *
            FROM transaction_orders
            WHERE ordinal_by_server_date != ordinal_by_client_date
        )
    );
END;
$$ LANGUAGE plpgsql;
