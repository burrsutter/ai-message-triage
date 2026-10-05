#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="message-triage"

oc delete -n "${NAMESPACE}" \
  -f "${ROOT_DIR}/openshift/backend/05-review-to-sales.yaml" \
  --ignore-not-found
