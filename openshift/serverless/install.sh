#!/usr/bin/env bash
#
# Installs Red Hat OpenShift Serverless (Knative):
# operator -> KnativeServing -> KnativeEventing. Idempotent; needs cluster-admin.
#
# Usage:  ./install.sh
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Cluster: $(oc whoami --show-server)  as  $(oc whoami)"

echo "==> 1/3 Installing OpenShift Serverless operator"
oc apply -f "${HERE}/01-operator.yaml"

echo "==> Waiting for the KnativeServing CRD to register (up to 5 min)..."
for i in $(seq 1 60); do
  oc get crd knativeservings.operator.knative.dev >/dev/null 2>&1 && { echo "    CRD present."; break; }
  sleep 5
  [ "$i" = "60" ] && { echo "ERROR: KnativeServing CRD not found."; exit 1; }
done
oc wait csv -n openshift-serverless \
  -l operators.coreos.com/serverless-operator.openshift-serverless \
  --for=jsonpath='{.status.phase}'=Succeeded --timeout=300s

echo "==> 2/3 Creating KnativeServing control plane"
oc apply -f "${HERE}/02-knative-serving.yaml"
oc wait knativeserving/knative-serving -n knative-serving --for=condition=Ready --timeout=300s

echo "==> 3/3 Creating KnativeEventing control plane"
oc apply -f "${HERE}/03-knative-eventing.yaml"
oc wait knativeeventing/knative-eventing -n knative-eventing --for=condition=Ready --timeout=300s

echo ""
echo "==> Done."
oc get knativeserving -n knative-serving
oc get knativeeventing -n knative-eventing
echo ""
oc get pods -n knative-serving
echo ""
oc get pods -n knative-eventing
