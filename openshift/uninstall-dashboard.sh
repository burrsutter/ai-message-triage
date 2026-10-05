#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="message-triage"
DASHBOARD_GIT_REF="${DASHBOARD_GIT_REF:-main}"
MANIFEST_BASE="https://raw.githubusercontent.com/burrsutter/ai-message-triage-dashboard/${DASHBOARD_GIT_REF}/openshift"

echo "==> Removing dashboard resources from ${NAMESPACE}"
oc delete -n "${NAMESPACE}" \
  -f "${MANIFEST_BASE}/03-application.yaml" \
  --ignore-not-found
oc delete -n "${NAMESPACE}" \
  -f "${MANIFEST_BASE}/02-build.yaml" \
  --ignore-not-found
oc delete -n "${NAMESPACE}" \
  -f "${MANIFEST_BASE}/01-configmap.yaml" \
  --ignore-not-found
