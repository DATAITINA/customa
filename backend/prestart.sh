#!/usr/bin/env bash

# Let the DB start
python ./app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Ensure required initial records exist without resetting existing tables/data.
python ./app/initial_data.py
