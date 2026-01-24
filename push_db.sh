#!/bin/bash

# Script to push the local database to the remote server

REMOTE_USER="syndicate"
REMOTE_HOST="betting.local"
REMOTE_PATH="/opt/betting-syndicate/betting_syndicate/database/betting_syndicate.db"
LOCAL_PATH="./database/betting_syndicate.db"

# Check if local database exists
if [ ! -f "${LOCAL_PATH}" ]; then
    echo "Local database not found at ${LOCAL_PATH}" >&2
    exit 1
fi

echo "WARNING: This will overwrite the database on ${REMOTE_HOST}"
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Pushing database to ${REMOTE_USER}@${REMOTE_HOST}..."

scp "${LOCAL_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

if [ $? -eq 0 ]; then
    echo "Database successfully uploaded to ${REMOTE_PATH}"
else
    echo "Failed to upload database" >&2
    exit 1
fi
