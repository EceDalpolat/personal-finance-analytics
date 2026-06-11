{#
    Classify actual spend against a budget limit. Returns a SQL CASE expression
    yielding 'over' / 'near' (>=90%) / 'under'. Keeps the threshold rule in one
    place so every mart labels budgets the same way.
#}
{% macro budget_status(actual, budget_limit) -%}
    case
        when {{ actual }} > {{ budget_limit }}            then 'over'
        when {{ actual }} >= 0.9 * {{ budget_limit }}     then 'near'
        else 'under'
    end
{%- endmacro %}
