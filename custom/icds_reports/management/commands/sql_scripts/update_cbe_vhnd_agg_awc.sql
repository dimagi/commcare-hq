UPDATE "%(tablename)s_5" agg_awc
SET
    cbe_conducted = ut.cbe_conducted,
    vhnd_conducted = ut.vhnd_conducted
from (
    select awc_location.doc_id as awc_id, cbe_conducted,vhnd_conducted
    FROM awc_location_local awc_location
     LEFT JOIN (
        select
            awc_id,
            count(*) as cbe_conducted from "ucr_icds-cas_static-cbe_form_f7988a04"
            WHERE date_trunc('MONTH', date_cbe_organise) = %(query_month)s
            GROUP BY awc_id
    ) cbe_table on  awc_location.doc_id = cbe_table.awc_id
    LEFT JOIN (
        SELECT awc_id,
                count(*) as vhnd_conducted from
                "ucr_icds-cas_static-vhnd_form_28e7fd58"
                WHERE date_trunc('MONTH', vhsnd_date_past_month) = %(query_month)s
                GROUP BY awc_id
        ) vhnd_table on awc_location.doc_id = vhnd_table.awc_id
) ut
WHERE agg_awc.awc_id = ut.awc_id;


UPDATE "%(tablename)s_4" agg_awc
SET
    cbe_conducted = ut.cbe_conducted,
    vhnd_conducted = ut.vhnd_conducted
FROM (
    select
        supervisor_id,
        sum(cbe_conducted) as cbe_conducted,
        sum(vhnd_conducted) as vhnd_conducted
    FROM "%(tablename)s_5"
    WHERE awc_is_test<>1
    GROUP by supervisor_id

) ut
WHERE agg_awc.supervisor_id = ut.supervisor_id;


UPDATE "%(tablename)s_3" agg_awc
SET
    cbe_conducted = ut.cbe_conducted,
    vhnd_conducted = ut.vhnd_conducted
FROM (
    select
        block_id,
        sum(cbe_conducted) as cbe_conducted,
        sum(vhnd_conducted) as vhnd_conducted
    FROM "%(tablename)s_4"
    WHERE awc_is_test<>1
    GROUP by block_id

) ut
WHERE agg_awc.block_id = ut.block_id;


UPDATE "%(tablename)s_2" agg_awc
SET
    cbe_conducted = ut.cbe_conducted,
    vhnd_conducted = ut.vhnd_conducted
FROM (
    select
        district_id,
        sum(cbe_conducted) as cbe_conducted,
        sum(vhnd_conducted) as vhnd_conducted
    FROM "%(tablename)s_3"
    WHERE block_is_test<>1
    GROUP by district_id

) ut
WHERE agg_awc.district_id = ut.district_id;


UPDATE "%(tablename)s_1" agg_awc
SET
    cbe_conducted = ut.cbe_conducted,
    vhnd_conducted = ut.vhnd_conducted
FROM (
    select
        state_id,
        sum(cbe_conducted) as cbe_conducted,
        sum(vhnd_conducted) as vhnd_conducted
    FROM "%(tablename)s_2"
    WHERE district_is_test<>1
    GROUP by state_id

) ut
WHERE agg_awc.state_id = ut.state_id;

