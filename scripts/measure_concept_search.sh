#!/usr/bin/env bash
# Measure concept search API response times.
# Usage: ./scripts/measure_concept_search.sh [query]

set -euo pipefail

QUERY="${1:-fire}"
BASE_URL="http://localhost:8080"
ITERATIONS=3

SUGGEST_URL="${BASE_URL}/api/concepts/suggest?q=${QUERY}"
CONCEPT_MAP_URL="${BASE_URL}/api/concept-map?concept=${QUERY}"

CURL_FORMAT='  HTTP %{http_code} | Total: %{time_total}s | Connect: %{time_connect}s | TTFB: %{time_starttransfer}s\n'

echo "=== Concept Search Performance ==="
echo "Query: \"${QUERY}\""
echo "Iterations: ${ITERATIONS}"
echo ""

echo "--- /api/concepts/suggest?q=${QUERY} ---"
for i in $(seq 1 "$ITERATIONS"); do
    printf "Run %d:" "$i"
    curl -s -o /dev/null -w "$CURL_FORMAT" "$SUGGEST_URL"
done

echo ""
echo "--- /api/concept-map?concept=${QUERY} ---"
for i in $(seq 1 "$ITERATIONS"); do
    printf "Run %d:" "$i"
    curl -s -o /dev/null -w "$CURL_FORMAT" "$CONCEPT_MAP_URL"
done
