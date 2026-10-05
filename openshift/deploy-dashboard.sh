#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="message-triage"
DASHBOARD_REPOSITORY="https://github.com/burrsutter/ai-message-triage-dashboard"
DASHBOARD_GIT_REF="${DASHBOARD_GIT_REF:-main}"
MANIFEST_BASE="https://raw.githubusercontent.com/burrsutter/ai-message-triage-dashboard/${DASHBOARD_GIT_REF}/openshift"

echo "==> Deploying dashboard from ${DASHBOARD_REPOSITORY}@${DASHBOARD_GIT_REF}"
oc apply -n "${NAMESPACE}" -f "${MANIFEST_BASE}/01-configmap.yaml"
oc apply -n "${NAMESPACE}" -f "${MANIFEST_BASE}/02-build.yaml"
oc patch buildconfig/message-triage-dashboard \
  -n "${NAMESPACE}" \
  --type=merge \
  -p "{\"spec\":{\"source\":{\"git\":{\"ref\":\"${DASHBOARD_GIT_REF}\"}}}}"

oc start-build message-triage-dashboard -n "${NAMESPACE}" --follow --wait

oc apply -n "${NAMESPACE}" -f "${MANIFEST_BASE}/03-application.yaml"
oc rollout restart deployment/message-triage-dashboard -n "${NAMESPACE}"
oc rollout status deployment/message-triage-dashboard \
  -n "${NAMESPACE}" \
  --timeout=300s

ROUTE_HOST="$(oc get route message-triage-dashboard -n "${NAMESPACE}" -o jsonpath='{.spec.host}')"
echo "==> Dashboard: https://${ROUTE_HOST}"
