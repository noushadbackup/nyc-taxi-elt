-- Every month present in the raw layer must produce trips in the fact table.
select raw_months.source_month
from (
    select distinct source_month from {{ source('raw', 'yellow_trips') }}
) as raw_months
left join (
    select distinct source_month from {{ ref('fct_trips') }}
) as fact_months
    on raw_months.source_month = fact_months.source_month
where fact_months.source_month is null
