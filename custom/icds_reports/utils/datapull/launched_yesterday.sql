
-- TO Fetch the list of awcs launched on 15th Dec night aggregation

select
    state_name,
    district_name,
    block_name,
    supervisor_name,
    awc_name,
    ucr.num_launched_awcs
from agg_awc_daily_view left join "agg_awc_2019-12-01_5" ucr
on agg_awc_daily_view.awc_id = ucr.awc_id
where agg_awc_daily_view.date='2019-12-12' and  -- using 12 because of a bug which causes last three days daily numbers to update
    agg_awc_daily_view.aggregation_level=5 and
    agg_awc_daily_view.num_launched_awcs<>1 and ucr.num_launched_awcs=1
