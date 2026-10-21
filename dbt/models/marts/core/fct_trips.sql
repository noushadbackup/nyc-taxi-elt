{#-
  Valid trips only, one row per trip. Incremental by month: each Airflow run
  rebuilds exactly the month it loaded, so re-runs and backfills are safe.
  On BigQuery the table is partitioned by pickup month and clustered by zone,
  so dashboards filtering on date and zone scan a fraction of the data.
-#}
{{
    config(
        materialized='incremental',
        incremental_strategy=('insert_overwrite' if target.type == 'bigquery' else 'delete+insert'),
        unique_key=(none if target.type == 'bigquery' else 'source_month'),
        partition_by=({'field': 'pickup_date', 'data_type': 'date', 'granularity': 'month'}
                      if target.type == 'bigquery' else none),
        cluster_by=(['pickup_zone_id', 'dropoff_zone_id'] if target.type == 'bigquery' else none),
        on_schema_change='append_new_columns',
    )
}}

with trips as (

    select * from {{ ref('int_trips_validated') }}
    where is_valid
      and {{ month_filter('source_month') }}

),

payment_types as (

    select * from {{ ref('payment_types') }}

)

select
    trips.trip_id,
    trips.source_month,
    trips.pickup_date,
    trips.pickup_at,
    trips.dropoff_at,
    extract(hour from trips.pickup_at)                 as pickup_hour,
    trips.pickup_zone_id,
    trips.dropoff_zone_id,
    trips.vendor_id,
    trips.rate_code_id,
    trips.payment_type_id,
    coalesce(payment_types.payment_type, 'Unknown')    as payment_type,
    trips.passenger_count,
    trips.trip_distance_miles,
    trips.trip_duration_seconds,
    round(trips.trip_distance_miles
          / nullif(trips.trip_duration_seconds / 3600.0, 0), 2) as avg_speed_mph,
    trips.fare_amount,
    trips.extra_amount,
    trips.mta_tax_amount,
    trips.tip_amount,
    trips.tolls_amount,
    trips.improvement_surcharge_amount,
    trips.congestion_surcharge_amount,
    trips.airport_fee_amount,
    trips.total_amount,
    trips.loaded_at
from trips
left join payment_types
    on trips.payment_type_id = payment_types.payment_type_id
