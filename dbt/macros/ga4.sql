{#
  GA4 helpers. Raw GA4 keeps its original calendar (2020-21); staging moves it into the simulation window.
#}

{# 'YYYYMMDD' string -> Date, shifted forward by var('ga4_shift_days') #}
{% macro ga4_date(column) -%}
    addDays(toDate(concat(substring({{ column }}, 1, 4), '-', substring({{ column }}, 5, 2), '-', substring({{ column }}, 7, 2))), {{ var('ga4_shift_days') }})
{%- endmacro %}

{# microsecond epoch -> UTC DateTime64, shifted by the same number of days #}
{% macro ga4_timestamp(column) -%}
    addDays(toTimeZone(fromUnixTimestamp64Micro({{ column }}), 'UTC'), {{ var('ga4_shift_days') }})
{%- endmacro %}

{#
  One value out of the event_params array: Array(Tuple(key, string_value, int_value, double_value)).
  value_field is string_value, int_value or double_value. No matching key gives NULL.
#}
{% macro ga4_param(key, value_field) -%}
    tupleElement(arrayFirst(p -> tupleElement(p, 'key') = '{{ key }}', event_params), '{{ value_field }}')
{%- endmacro %}
