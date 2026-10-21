{#-
  Restrict an incremental model to the month being processed.
  - var('month') set (Airflow runs): only that month
  - incremental run without the var: months newer than what the table holds
  - full refresh: everything
-#}
{% macro month_filter(column='source_month') -%}
    {%- if var('month') -%}
        {{ column }} = cast('{{ var("month") }}' as date)
    {%- elif is_incremental() -%}
        {{ column }} > (select coalesce(max({{ column }}), cast('1900-01-01' as date)) from {{ this }})
    {%- else -%}
        1 = 1
    {%- endif -%}
{%- endmacro %}
