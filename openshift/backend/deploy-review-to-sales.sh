#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENSHIFT_DIR="${ROOT_DIR}/openshift/backend"
NAMESPACE="message-triage"

oc get imagestream message-triage-backend -n "${NAMESPACE}" >/dev/null
oc get configmap message-triage-review-to-sales -n "${NAMESPACE}" >/dev/null
oc get secret message-triage-model-credentials -n "${NAMESPACE}" >/dev/null

echo "==> Adding the review-to-sales exception handler"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/05-review-to-sales.yaml"
oc rollout status deployment/message-triage-review-to-sales \
  -n "${NAMESPACE}" --timeout=300s

echo "==> Review exceptions can now be routed to the sales topic"
oc get pod -n "${NAMESPACE}" \
  -l app.kubernetes.io/name=message-triage-review-to-sales
