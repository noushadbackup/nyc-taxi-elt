select
    zone_id,
    zone_name,
    borough,
    service_zone,
    zone_name in ('JFK Airport', 'LaGuardia Airport', 'Newark Airport') as is_airport
from {{ ref('stg_taxi_zones') }}
