#!/usr/bin/env bash
#
# Installs Red Hat OpenShift Service Mesh 3 (upstream Istio / Sail operator):
# operator -> IstioCNI -> Istio control plane. Idempotent; needs cluster-admin.
#
# Usage:  ./install.sh
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Cluster: $(oc whoami --show-server)  as  $(oc whoami)"

echo "==> 1/4 Installing Service Mesh 3 operator"
oc apply -f "${HERE}/01-subscription.yaml"

echo "==> Waiting for the Istio CRD to register (up to 5 min)..."
for i in $(seq 1 60); do
  oc get crd istios.sailoperator.io >/dev/null 2>&1 && { echo "    CRD present."; break; }
  sleep 5
  [ "$i" = "60" ] && { echo "ERROR: Istio CRD not found."; exit 1; }
done
oc wait csv -n openshift-operators \
  -l operators.coreos.com/servicemeshoperator3.openshift-operators \
  --for=jsonpath='{.status.phase}'=Succeeded --timeout=300s

echo "==> 2/4 Creating namespaces (istio-cni, istio-system)"
oc apply -f "${HERE}/02-namespaces.yaml"

echo "==> 3/4 Creating IstioCNI"
oc apply -f "${HERE}/03-istio-cni.yaml"
oc wait istiocni/default --for=condition=Ready --timeout=300s

echo "==> 4/4 Creating Istio control plane"
oc apply -f "${HERE}/04-istio.yaml"
oc wait istio/default --for=condition=Ready --timeout=300s

echo ""
echo "==> Done."
oc get istio,istiocni
echo ""
oc get pods -n istio-system
oc get pods -n istio-cni
echo ""
echo "The mesh is empty. Enroll a namespace with:"
echo "  oc label namespace <ns> istio-injection=enabled"
echo "then restart its workloads so sidecars get injected."
