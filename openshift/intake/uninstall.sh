#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="message-triage"

oc delete route,service,deployment,buildconfig,imagestream \
  -n "${NAMESPACE}" \
  -l app.kubernetes.io/name=message-triage-http-intake \
  --ignore-not-found
oc delete configmap \
  -n "${NAMESPACE}" \
  message-triage-http-intake \
  message-triage-http-intake-build-intake \
  message-triage-http-intake-build-models \
  --ignore-not-found
