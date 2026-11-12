{#
  Use the layer name as the ClickHouse database ("staging", "intermediate", "marts").
  dbt's default would prefix the target schema ("staging_marts"), which is not what we want here.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
