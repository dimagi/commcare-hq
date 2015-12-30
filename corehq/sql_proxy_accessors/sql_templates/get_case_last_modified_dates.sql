DROP FUNCTION IF EXISTS get_case_last_modified_dates(TEXT, TEXT[]);

CREATE FUNCTION get_case_last_modified_dates(domain_name TEXT, case_ids TEXT[])
RETURNS TABLE (case_id VARCHAR(255), server_modified_on timestamp with time zone ) AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    SPLIT case_ids;
    RUN ON hash_string(case_ids, 'siphash24');
$$ LANGUAGE plproxy;


