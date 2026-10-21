{#- Daily KPIs per pickup borough: the table a dashboard would sit on. -#}
with trips as (

    select * from {{ ref('fct_trips') }}

),

zones as (

    select * from {{ ref('dim_zones') }}

)

select
    trips.pickup_date,
    zones.borough                                         as pickup_borough,
    count(*)                                              as trip_count,
    sum(trips.passenger_count)                            as passenger_count,
    sum(trips.total_amount)                               as total_revenue,
    round(avg(trips.total_amount), 2)                     as avg_total_amount,
    round(avg(trips.trip_distance_miles), 2)              as avg_trip_distance_miles,
    round(avg(trips.trip_duration_seconds) / 60.0, 1)     as avg_trip_duration_minutes,
    -- Tips are only recorded for card payments, so tip rate is card trips only.
    round(
        sum(case when trips.payment_type_id = 1 then trips.tip_amount end)
        / nullif(sum(case when trips.payment_type_id = 1 then trips.fare_amount end), 0),
        4
    )                                                     as card_tip_rate,
    sum(case when zones.is_airport then 1 else 0 end)     as airport_pickups
from trips
inner join zones
    on trips.pickup_zone_id = zones.zone_id
group by 1, 2
