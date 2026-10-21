-- Guards against a broken or truncated source file: fails when more than
-- var('max_invalid_trip_ratio') of a month's trips are rejected by the DQ rules.
select
    source_month,
    1 - sum(case when dq_status = 'valid' then share_of_month else 0 end) as invalid_ratio
from {{ ref('mart_data_quality_monthly') }}
group by 1
having 1 - sum(case when dq_status = 'valid' then share_of_month else 0 end) > {{ var('max_invalid_trip_ratio') }}
