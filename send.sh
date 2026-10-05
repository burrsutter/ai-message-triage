#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLE_DIR="${ROOT_DIR}/data/sample"
NAMESPACE="message-triage"
ROUTE_NAME="message-triage-http-intake"

usage() {
  cat <<'EOF'
Send a sample message to the OpenShift HTTP intake service.

Run this script from the ai-message-triage repository root:

  ./send.sh <category/message-file>
  ./send.sh --list

Examples:

  ./send.sh finance/missing-invoice.txt
  ./send.sh support/technical-support-1.txt
  ./send.sh website/help-password-1.txt

Set HTTP_INTAKE_URL to override OpenShift Route discovery.
EOF
}

list_samples() {
  find "${SAMPLE_DIR}" -mindepth 2 -maxdepth 2 -type f \
    | sed "s#^${SAMPLE_DIR}/##" \
    | sort
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

if [[ "$1" == "--list" ]]; then
  list_samples
  exit 0
fi

SAMPLE_NAME="$1"
if [[ "${SAMPLE_NAME}" == /* || "${SAMPLE_NAME}" == *".."* ]]; then
  echo "ERROR: choose a relative path reported by ./send.sh --list" >&2
  exit 2
fi

MESSAGE_PATH="${SAMPLE_DIR}/${SAMPLE_NAME}"
if [[ ! -f "${MESSAGE_PATH}" ]]; then
  echo "ERROR: sample not found: ${SAMPLE_NAME}" >&2
  echo "Available samples:" >&2
  list_samples >&2
  exit 2
fi

if [[ -n "${HTTP_INTAKE_URL:-}" ]]; then
  INTAKE_URL="${HTTP_INTAKE_URL%/}"
else
  ROUTE_HOST="$(
    oc get route "${ROUTE_NAME}" \
      -n "${NAMESPACE}" \
      -o jsonpath='{.spec.host}'
  )"
  INTAKE_URL="https://${ROUTE_HOST}"
fi

MESSAGE_FILENAME="$(basename "${MESSAGE_PATH}")"
echo "Sending ${SAMPLE_NAME} to ${INTAKE_URL}/intake"

curl --fail-with-body --silent --show-error \
  --request POST "${INTAKE_URL}/intake" \
  --form "file=@${MESSAGE_PATH};filename=${MESSAGE_FILENAME};type=text/plain"
echo
