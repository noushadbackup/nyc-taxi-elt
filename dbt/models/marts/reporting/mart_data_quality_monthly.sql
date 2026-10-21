{#- How many trips each data quality rule rejected, per source file. -#}
select
    source_month,
    coalesce(dq_issue, 'valid')                                      as dq_status,
    count(*)                                                         as trip_count,
    round(count(*) * 1.0 / sum(count(*)) over (partition by source_month), 4) as share_of_month
from {{ ref('int_trips_validated') }}
group by 1, 2
