#!/usr/bin/env bash
#
# Tears down OpenShift Serverless (Knative).
#
# Usage:
#   ./uninstall.sh          # remove Serving + Eventing control planes
#   ./uninstall.sh --all    # also remove the operator subscription/CSV/namespace
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Removing KnativeEventing and KnativeServing control planes"
oc delete -f "${HERE}/03-knative-eventing.yaml" --ignore-not-found
oc delete -f "${HERE}/02-knative-serving.yaml" --ignore-not-found

if [ "${1:-}" = "--all" ]; then
  echo "==> Removing the Serverless operator"
  oc delete -f "${HERE}/01-operator.yaml" --ignore-not-found
  CSV="$(oc get csv -n openshift-serverless -o name 2>/dev/null | grep serverless-operator || true)"
  [ -n "$CSV" ] && oc delete "$CSV" -n openshift-serverless --ignore-not-found
  echo "    Note: shared operator.knative.dev CRDs are left in place by design."
fi

echo "==> Done."
