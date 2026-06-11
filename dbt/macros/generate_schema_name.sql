{#
    Use the custom +schema config verbatim as the schema name, instead of dbt's
    default "<target_schema>_<custom>" prefixing. This gives clean schemas:
    staging / marts / ai_layer. Models with no custom schema fall back to the
    target schema (analytics).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
