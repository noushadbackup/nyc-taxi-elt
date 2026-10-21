{#-
  One row per trip, renamed and typed. Exact duplicate records (which do occur
  in the TLC files) are collapsed here, so trip_id is unique downstream.
-#}
with source as (

    select * from {{ source('raw', 'yellow_trips') }}

),

renamed as (

    select
        {{ dbt.hash(dbt.concat([
            "coalesce(cast(vendorid as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(tpep_pickup_datetime as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(tpep_dropoff_datetime as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(pulocationid as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(dolocationid as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(trip_distance as " ~ dbt.type_string() ~ "), '')",
            "coalesce(cast(total_amount as " ~ dbt.type_string() ~ "), '')",
        ])) }}                                      as trip_id,

        cast(vendorid as {{ dbt.type_int() }})     as vendor_id,
        cast(ratecodeid as {{ dbt.type_int() }})   as rate_code_id,
        cast(pulocationid as {{ dbt.type_int() }}) as pickup_zone_id,
        cast(dolocationid as {{ dbt.type_int() }}) as dropoff_zone_id,
        cast(payment_type as {{ dbt.type_int() }}) as payment_type_id,
        store_and_fwd_flag = 'Y'                   as is_store_and_forward,

        tpep_pickup_datetime                       as pickup_at,
        tpep_dropoff_datetime                      as dropoff_at,

        passenger_count,
        trip_distance                              as trip_distance_miles,

        {{ cents('fare_amount') }}                 as fare_amount,
        {{ cents('extra') }}                       as extra_amount,
        {{ cents('mta_tax') }}                     as mta_tax_amount,
        {{ cents('tip_amount') }}                  as tip_amount,
        {{ cents('tolls_amount') }}                as tolls_amount,
        {{ cents('improvement_surcharge') }}       as improvement_surcharge_amount,
        {{ cents('congestion_surcharge') }}        as congestion_surcharge_amount,
        {{ cents('airport_fee') }}                 as airport_fee_amount,
        {{ cents('total_amount') }}                as total_amount,

        source_month,
        _loaded_at                                 as loaded_at

    from source

),

deduplicated as (

    select
        *,
        row_number() over (partition by trip_id order by loaded_at desc) as _row_num
    from renamed

)

select * {{ 'except' if target.type == 'bigquery' else 'exclude' }} (_row_num)
from deduplicated
where _row_num = 1
