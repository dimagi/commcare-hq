DROP FUNCTION IF EXISTS {{ sql_function_name }}(TEXT);

-- RUN ON ALL must return SETOF
CREATE FUNCTION {{ sql_function_name }}(args TEXT) RETURNS SETOF <type|tablename> AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON <ALL|hash_string>;
$$ LANGUAGE plproxy;

