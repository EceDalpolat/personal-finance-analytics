FROM python:3.13-slim

WORKDIR /app

# dbt Core 1.9 (postgres adapter). Pinned for reproducible builds.
RUN pip install --no-cache-dir "dbt-postgres==1.9.0"

COPY . .

# Fetch packages (dbt_utils) at build time; the profile isn't needed for deps.
RUN dbt deps

ENV DBT_PROFILES_DIR=/app
ENTRYPOINT ["dbt"]
CMD ["build"]
