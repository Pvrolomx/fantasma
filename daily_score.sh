#!/bin/bash
# OBSERVATORIO - Daily cron script
# Runs at 6:45 AM CT (12:45 UTC)
# Saves daily snapshot to data/history/

cd /home/pvrolo/repos/fantasma/api
python3 -c "
import asyncio
from history import run_and_save
asyncio.run(run_and_save())
" >> /home/pvrolo/repos/fantasma/data/cron.log 2>&1
echo "---" >> /home/pvrolo/repos/fantasma/data/cron.log
