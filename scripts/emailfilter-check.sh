#!/bin/bash

EMAIL="$1"

RESPONSE=$(curl -s -X POST "http://localhost:8000/filter-email" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\"}")

# Parse JSON fields (requires jq)
if command -v jq > /dev/null; then
    VALID=$(echo "$RESPONSE" | jq -r '.valid_syntax and .domain_exists and .mx_records_found and (.is_blacklisted | not)')
else
    # fallback: basic grep
    echo "$RESPONSE" | grep -q '"valid_syntax": true' &&
    echo "$RESPONSE" | grep -q '"domain_exists": true' &&
    echo "$RESPONSE" | grep -q '"mx_records_found": true' &&
    ! echo "$RESPONSE" | grep -q '"is_blacklisted": true'
    VALID=$?
fi

if [ "$VALID" == "true" ] || [ "$VALID" == "0" ]; then
    echo "$EMAIL"
else
    exit 1
fi
