{#- Round a money amount to cents in a warehouse-neutral way. -#}
{% macro cents(expr) -%}
    round(cast({{ expr }} as {{ dbt.type_numeric() }}), 2)
{%- endmacro %}
