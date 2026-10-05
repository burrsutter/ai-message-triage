#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENSHIFT_DIR="${ROOT_DIR}/openshift/backend"
NAMESPACE="message-triage"

oc get secret message-triage-model-credentials -n "${NAMESPACE}" >/dev/null

create_source_configmap() {
  local name="$1"
  local destination="$2"
  shift 2

  local args=()
  local source_file
  for source_file in "$@"; do
    args+=(--from-file="${ROOT_DIR}/${destination}/${source_file}")
  done

  oc create configmap "${name}" -n "${NAMESPACE}" \
    "${args[@]}" --dry-run=client -o yaml \
    | oc apply -n "${NAMESPACE}" -f -
}

echo "==> Creating backend build context in ${NAMESPACE}"
oc create configmap message-triage-backend-build-root -n "${NAMESPACE}" \
  --from-file="${ROOT_DIR}/requirements-backend.txt" \
  --dry-run=client -o yaml \
  | oc apply -n "${NAMESPACE}" -f -

create_source_configmap message-triage-backend-build-models models __init__.py
create_source_configmap message-triage-backend-build-structure structure __init__.py message-structure.py
create_source_configmap message-triage-backend-build-guardian guardian __init__.py classifier.py message-guardian.py
create_source_configmap message-triage-backend-build-customer customer __init__.py customer-lookup.py
create_source_configmap message-triage-backend-build-router router __init__.py message-router.py
create_source_configmap message-triage-backend-build-support support __init__.py support-responder.py
create_source_configmap message-triage-backend-build-finance finance __init__.py finance-responder.py finance-api.py finance_models.py
create_source_configmap message-triage-backend-build-website website __init__.py website-support.py website-api.py password_models.py
create_source_configmap message-triage-backend-build-opportunity opportunity __init__.py opportunity-finder.py

oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/01-configmaps.yaml"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/02-build.yaml"

echo "==> Building the shared backend runtime image"
oc start-build message-triage-backend -n "${NAMESPACE}" --follow --wait

echo "==> Deploying independent agent and tool API pods"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/04-tool-apis.yaml"
oc apply -n "${NAMESPACE}" -f "${OPENSHIFT_DIR}/03-agents.yaml"

deployments=(
  message-triage-finance-api
  message-triage-website-api
  message-triage-structure
  message-triage-guardian
  message-triage-customer
  message-triage-router
  message-triage-support
  message-triage-finance
  message-triage-website
)

echo "==> Restarting backend pods to pull the newly built image"
for deployment in "${deployments[@]}"; do
  oc rollout restart "deployment/${deployment}" -n "${NAMESPACE}"
done

for deployment in "${deployments[@]}"; do
  oc rollout status "deployment/${deployment}" -n "${NAMESPACE}" --timeout=300s
done

echo "==> Backend pods"
oc get pods -n "${NAMESPACE}" -l app.kubernetes.io/component=agent
oc get pods -n "${NAMESPACE}" -l app.kubernetes.io/component=tool-api
echo "==> Later demo step: ./openshift/backend/deploy-review-to-sales.sh"
