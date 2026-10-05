#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="message-triage"

echo "==> Deploying ai-message-triage to ${NAMESPACE}"
if oc get kafka message-triage-kafka -n "${NAMESPACE}" >/dev/null 2>&1; then
  echo "==> Kafka already exists in ${NAMESPACE}; leaving it in place"
else
  "${HERE}/kafka/install.sh"
fi
"${HERE}/backend/deploy.sh"
"${HERE}/intake/deploy.sh"
"${HERE}/deploy-dashboard.sh"

echo "==> Application workloads in ${NAMESPACE}"
oc get deployments -n "${NAMESPACE}"
echo "==> Demo routes"
oc get routes -n "${NAMESPACE}"
