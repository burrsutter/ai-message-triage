#!/usr/bin/env bash
#
# Tears down OpenShift Service Mesh 3.
#
# Usage:
#   ./uninstall.sh          # remove control plane + CNI + namespaces
#   ./uninstall.sh --all    # also remove the operator subscription/CSV
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Removing Istio control plane and IstioCNI"
oc delete -f "${HERE}/04-istio.yaml" --ignore-not-found
oc delete -f "${HERE}/03-istio-cni.yaml" --ignore-not-found

echo "==> Removing namespaces"
oc delete -f "${HERE}/02-namespaces.yaml" --ignore-not-found

if [ "${1:-}" = "--all" ]; then
  echo "==> Removing the Service Mesh 3 operator"
  oc delete -f "${HERE}/01-subscription.yaml" --ignore-not-found
  CSV="$(oc get csv -n openshift-operators -o name 2>/dev/null | grep servicemeshoperator3 || true)"
  [ -n "$CSV" ] && oc delete "$CSV" -n openshift-operators --ignore-not-found
  echo "    Note: shared sailoperator.io CRDs are left in place by design."
fi

echo "==> Done."
