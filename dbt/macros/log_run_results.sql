{#
  on-run-end: one row per model, seed, snapshot and test in meta.dbt_run_results, so the Insights Hub
  (Pipeline Health) and the AI triage agent can see what ran, how long it took and what failed.
#}
{% macro log_run_results(results) %}
    {% if execute and results %}
        {% do run_query("
            create table if not exists meta.dbt_run_results (
                invocation_id String,
                run_started_at DateTime64(3, 'UTC'),
                logged_at DateTime64(3, 'UTC') default now64(3),
                node_id String,
                resource_type LowCardinality(String),
                node_name String,
                status LowCardinality(String),
                execution_time_s Float64,
                failures Nullable(Int64),
                message String
            ) engine = MergeTree order by (run_started_at, node_id)
        ") %}
        {% set rows = [] %}
        {% for r in results %}
            {% set msg = (r.message or '') | string | replace('\\', '\\\\') | replace("'", "\\'") %}
            {% do rows.append(
                "('" ~ invocation_id ~ "', '" ~ run_started_at.strftime('%Y-%m-%d %H:%M:%S') ~ "', '"
                ~ r.node.unique_id ~ "', '" ~ r.node.resource_type ~ "', '" ~ r.node.name ~ "', '"
                ~ r.status ~ "', " ~ (r.execution_time or 0) ~ ", "
                ~ (r.failures if r.failures is not none else 'null') ~ ", '" ~ msg[:500] ~ "')"
            ) %}
        {% endfor %}
        {% do run_query(
            "insert into meta.dbt_run_results (invocation_id, run_started_at, node_id, resource_type, node_name, "
            ~ "status, execution_time_s, failures, message) values " ~ rows | join(', ')
        ) %}
    {% endif %}
{% endmacro %}
