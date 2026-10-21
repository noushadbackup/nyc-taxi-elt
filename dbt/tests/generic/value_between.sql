{#- Fails for rows where the column falls outside [min_value, max_value]. Nulls are ignored. -#}
{% test value_between(model, column_name, min_value=none, max_value=none, inclusive_min=true, inclusive_max=true) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and (
      1 = 0
      {%- if min_value is not none %}
      or {{ column_name }} {{ '<' if inclusive_min else '<=' }} {{ min_value }}
      {%- endif %}
      {%- if max_value is not none %}
      or {{ column_name }} {{ '>' if inclusive_max else '>=' }} {{ max_value }}
      {%- endif %}
  )

{% endtest %}
