#!/bin/bash
# Cron entry point for MCR cognitive tick
# Usage: */1 * * * * /home/minimak/mcr/tick.sh >> /home/minimak/mcr/cron.log 2>&1

cd /home/minimak/mcr
python3 loop.py >> /home/minimak/mcr/cron.log 2>&1
