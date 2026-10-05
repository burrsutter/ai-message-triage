#!/usr/bin/env bash
#
# Tears down the Kafka cluster (and optionally the operator) for ai-message-triage.
#
# Usage:
#   ./uninstall.sh            # remove topics + Kafka cluster + node pool + namespace
#   ./uninstall.sh --all      # also remove the AMQ Streams operator subscription/CSV
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Deleting topics, Kafka cluster and node pool in namespace 'message-triage'"
oc delete -f "${HERE}/05-kafka-topics.yaml" --ignore-not-found
oc delete -f "${HERE}/04-kafka-cluster.yaml" --ignore-not-found
oc delete -f "${HERE}/03-kafka-node-pool.yaml" --ignore-not-found

echo "==> Deleting namespace 'message-triage' (this also removes the PVC since deleteClaim: true)"
oc delete -f "${HERE}/02-namespace.yaml" --ignore-not-found

if [ "${1:-}" = "--all" ]; then
  echo "==> Removing the AMQ Streams operator"
  oc delete -f "${HERE}/01-subscription.yaml" --ignore-not-found
  # Remove the installed CSV (name contains the version)
  CSV="$(oc get csv -n openshift-operators -o name 2>/dev/null | grep amqstreams || true)"
  [ -n "$CSV" ] && oc delete "$CSV" -n openshift-operators --ignore-not-found
  echo "    Note: shared Strimzi CRDs are left in place by design."
fi

echo "==> Done."
