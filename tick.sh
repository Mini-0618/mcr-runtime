#!/bin/bash
# Cron entry point for MCR cognitive tick
# Usage: */1 * * * * ./tick.sh >> ./cron.log 2>&1

cd .
python3 loop.py >> ./cron.log 2>&1
