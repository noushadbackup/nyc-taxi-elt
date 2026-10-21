-- The daily aggregate must account for every cent in fct_trips:
-- returns the days where the two disagree by more than a cent.
with fact as (

    select pickup_date, sum(total_amount) as revenue
    from {{ ref('fct_trips') }}
    group by 1

),

agg as (

    select pickup_date, sum(total_revenue) as revenue
    from {{ ref('agg_daily_borough_metrics') }}
    group by 1

)

select
    fact.pickup_date,
    fact.revenue as fact_revenue,
    agg.revenue  as agg_revenue
from fact
full outer join agg
    on fact.pickup_date = agg.pickup_date
where agg.pickup_date is null
   or fact.pickup_date is null
   or abs(fact.revenue - agg.revenue) > 0.01
