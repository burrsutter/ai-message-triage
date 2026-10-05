#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENSHIFT_DIR="${ROOT_DIR}/openshift/backend"
NAMESPACE="message-triage"

oc delete -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/05-review-to-sales.yaml" --ignore-not-found
oc delete -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/03-agents.yaml" --ignore-not-found
oc delete -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/04-tool-apis.yaml" --ignore-not-found
oc delete -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/02-build.yaml" --ignore-not-found
oc delete -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/01-configmaps.yaml" --ignore-not-found
oc delete configmap -n "${NAMESPACE}" \
  message-triage-backend-build-root \
  message-triage-backend-build-models \
  message-triage-backend-build-structure \
  message-triage-backend-build-guardian \
  message-triage-backend-build-customer \
  message-triage-backend-build-router \
  message-triage-backend-build-support \
  message-triage-backend-build-finance \
  message-triage-backend-build-website \
  message-triage-backend-build-opportunity \
  --ignore-not-found
