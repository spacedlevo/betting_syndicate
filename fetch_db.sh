#!/bin/bash

# Script to retrieve the database from the remote server

REMOTE_USER="syndicate"
REMOTE_HOST="betting.local"
REMOTE_PATH="/opt/betting-syndicate/betting_syndicate/database/betting_syndicate.db"
LOCAL_PATH="./database/betting_syndicate.db"

echo "Fetching database from ${REMOTE_USER}@${REMOTE_HOST}..."

scp "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}" "${LOCAL_PATH}"

if [ $? -eq 0 ]; then
    echo "Database successfully downloaded to ${LOCAL_PATH}"
else
    echo "Failed to download database" >&2
    exit 1
fi
