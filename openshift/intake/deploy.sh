#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENSHIFT_DIR="${ROOT_DIR}/openshift/intake"
NAMESPACE="message-triage"

echo "==> Creating the HTTP intake build context"
oc create configmap message-triage-http-intake-build-intake \
  -n "${NAMESPACE}" \
  --from-file="${ROOT_DIR}/intake/__init__.py" \
  --from-file="${ROOT_DIR}/intake/http_intake.py" \
  --from-file="${ROOT_DIR}/intake/processor.py" \
  --from-file="${ROOT_DIR}/intake/requirements.txt" \
  --dry-run=client \
  -o yaml | oc apply -n "${NAMESPACE}" -f -

oc create configmap message-triage-http-intake-build-models \
  -n "${NAMESPACE}" \
  --from-file="${ROOT_DIR}/models/__init__.py" \
  --dry-run=client \
  -o yaml | oc apply -n "${NAMESPACE}" -f -

oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/01-configmap.yaml"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/02-build.yaml"

echo "==> Building the HTTP intake image"
oc start-build message-triage-http-intake -n "${NAMESPACE}" --follow --wait

echo "==> Deploying the HTTP intake service and TLS route"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/03-application.yaml"
oc rollout restart deployment/message-triage-http-intake -n "${NAMESPACE}"
oc rollout status deployment/message-triage-http-intake -n "${NAMESPACE}" --timeout=300s

ROUTE_HOST="$(oc get route message-triage-http-intake -n "${NAMESPACE}" -o jsonpath='{.spec.host}')"
echo "==> HTTP intake: https://${ROUTE_HOST}/intake"
