#!/bin/bash
# Simple milter script for PMG to verify sender email addresses with emailfilter

while read line; do
    # Parse the SMTP 'MAIL FROM' command to extract the sender email
    if [[ "$line" =~ ^MAIL\ FROM:\<(.*)\> ]]; then
        sender="${BASH_REMATCH[1]}"
        # Query emailfilter
        response=$(curl -s -X POST "http://localhost:8000/filter-email" \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$sender\"}")
        # Extract verification status from response (assuming JSON with "valid": true/false)
        valid=$(echo "$response" | grep -Po '(?<="valid":)[^,}]*')

        if [[ "$valid" != "true" ]]; then
            # Reject sender if invalid
            echo "550 5.7.1 Sender address rejected by emailfilter"
            exit 1
        fi
    fi
done
exit 0
