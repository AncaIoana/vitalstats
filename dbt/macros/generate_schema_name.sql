{% macro generate_schema_name(custom_schema_name, node) -%}
    {#
        Override dbt's default schema naming behaviour.

        Default behaviour: target_schema + '_' + custom_schema_name
        e.g. profiles.yml schema=silver + dbt_project.yml +schema=silver → silver_silver

        This override: use custom_schema_name directly when set, otherwise
        fall back to the target schema from profiles.yml.

        Result: +schema: silver → silver (not silver_silver)
    #}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
