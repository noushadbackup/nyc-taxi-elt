{#-
  Applies the data quality rules to every trip. Nothing is dropped here:
  each trip gets is_valid plus the first rule it broke, so the rejected rows
  stay queryable (see mart_data_quality_monthly).
-#}
with trips as (

    select * from {{ ref('stg_yellow_trips') }}

),

enriched as (

    select
        *,
        cast(pickup_at as date) as pickup_date,
        {{ dbt.datediff('pickup_at', 'dropoff_at', 'second') }} as trip_duration_seconds,
        cast({{ dbt.date_trunc('month', 'pickup_at') }} as date) as pickup_month
    from trips

),

flagged as (

    select
        *,
        case
            when pickup_month != source_month           then 'pickup_outside_file_month'
            when dropoff_at <= pickup_at                then 'non_positive_duration'
            when trip_duration_seconds > 6 * 60 * 60    then 'duration_over_6h'
            when trip_distance_miles <= 0               then 'non_positive_distance'
            when trip_distance_miles > 200              then 'distance_over_200mi'
            when fare_amount < 0 or total_amount < 0    then 'negative_amount'
            when total_amount > 1000                    then 'total_over_1000'
            when pickup_zone_id is null
              or dropoff_zone_id is null                then 'missing_zone'
        end as dq_issue
    from enriched

)

select
    *,
    dq_issue is null as is_valid
from flagged
