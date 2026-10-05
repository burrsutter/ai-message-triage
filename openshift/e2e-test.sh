#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="message-triage"
KAFKA_POD="message-triage-kafka-kafka-dual-role-0"
KAFKA_BOOTSTRAP="message-triage-kafka-kafka-bootstrap:9092"
KAFKA_CONSUMER="/opt/kafka/bin/kafka-console-consumer.sh"
RESULTS_ROOT="${E2E_RESULTS_ROOT:-${ROOT_DIR}/test-results}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RESULTS_ROOT}/e2e-${RUN_ID}"
TOPICS_DIR="${RUN_DIR}/topics"
LOGS_DIR="${RUN_DIR}/logs"
POLL_DIR="${RUN_DIR}/poll"
TIMEOUT_SECONDS="${E2E_TIMEOUT_SECONDS:-2400}"
POLL_SECONDS="${E2E_POLL_SECONDS:-15}"
TOPIC_QUIET_MS="${E2E_TOPIC_QUIET_MS:-3000}"

TOPICS=(
  intake
  structured
  cleared
  ready
  support
  finance
  website
  outflow
  review
  sales
)

LOG_DEPLOYMENTS=(
  message-triage-http-intake
  message-triage-structure
  message-triage-guardian
  message-triage-customer
  message-triage-router
  message-triage-support
  message-triage-finance
  message-triage-finance-api
  message-triage-website
  message-triage-website-api
  message-triage-review-to-sales
  message-triage-dashboard
)

usage() {
  cat <<'EOF'
Run every sample through the OpenShift message-triage pipeline, validate the
Kafka topics visited by each filename, save a report, and reset the demo.

Usage:
  ./openshift/e2e-test.sh

Optional environment variables:
  E2E_TIMEOUT_SECONDS   Maximum wait for each pipeline phase (default: 2400)
  E2E_POLL_SECONDS      Delay between Kafka checks (default: 15)
  E2E_TOPIC_QUIET_MS    Kafka capture idle timeout (default: 3000)
  E2E_RESULTS_ROOT      Report directory (default: ./test-results)
EOF
}

if [[ $# -gt 0 ]]; then
  if [[ $# -eq 1 && "$1" == "--help" ]]; then
    usage
    exit 0
  fi
  usage >&2
  exit 2
fi

mkdir -p "${TOPICS_DIR}" "${LOGS_DIR}" "${POLL_DIR}"

cleanup_complete=false

cleanup() {
  local original_status="$1"
  local reset_status
  local dashboard_host
  trap - EXIT INT TERM
  set +e

  echo
  echo "==> Resetting the demo after the test"
  "${ROOT_DIR}/openshift/reset-demo.sh" >"${RUN_DIR}/reset-after.log" 2>&1
  reset_status=$?
  if [[ ${reset_status} -eq 0 ]]; then
    cleanup_complete=true
    echo "PASS" >"${RUN_DIR}/cleanup-status.txt"
    oc get deployments,pods,kafka,kafkatopic -n "${NAMESPACE}" \
      >"${RUN_DIR}/post-reset-state.log" 2>&1 || true
    echo "==> Cleanup complete; the initial demo topology is ready"
  else
    echo "FAIL" >"${RUN_DIR}/cleanup-status.txt"
    echo "ERROR: post-test reset failed; see ${RUN_DIR}/reset-after.log" >&2
    original_status=1
  fi

  if [[ -f "${RUN_DIR}/summary.md" ]]; then
    echo "Results: ${RUN_DIR}/summary.md"
  else
    echo "The test stopped before a summary could be generated."
  fi
  echo "Full run artifacts: ${RUN_DIR}"
  if [[ "${cleanup_complete}" == "true" ]]; then
    dashboard_host="$(oc get route message-triage-dashboard -n "${NAMESPACE}" \
      -o jsonpath='{.spec.host}' 2>/dev/null)"
    if [[ -n "${dashboard_host}" ]] && \
      curl -fsS --max-time 10 "https://${dashboard_host}/api/status" 2>/dev/null \
        | jq -e '.resetAware == true' >/dev/null 2>&1; then
      echo "The dashboard will clear its cards when it reconnects to the restarted dashboard pod."
    else
      echo "Refresh the dashboard or click Clear All Messages to clear browser-local cards."
    fi
  fi
  exit "${original_status}"
}

for command_name in oc curl jq python3; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "ERROR: required command not found: ${command_name}" >&2
    exit 2
  fi
done

if ! [[ "${TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] || [[ "${TIMEOUT_SECONDS}" -lt 1 ]]; then
  echo "ERROR: E2E_TIMEOUT_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! [[ "${POLL_SECONDS}" =~ ^[0-9]+$ ]] || [[ "${POLL_SECONDS}" -lt 1 ]]; then
  echo "ERROR: E2E_POLL_SECONDS must be a positive integer" >&2
  exit 2
fi
if ! [[ "${TOPIC_QUIET_MS}" =~ ^[0-9]+$ ]] || [[ "${TOPIC_QUIET_MS}" -lt 1 ]]; then
  echo "ERROR: E2E_TOPIC_QUIET_MS must be a positive integer" >&2
  exit 2
fi

find "${ROOT_DIR}/data/sample" -mindepth 2 -maxdepth 2 -type f \
  | sed "s#^${ROOT_DIR}/data/sample/##" \
  | sort >"${RUN_DIR}/samples.txt"

sed 's#^.*/##' "${RUN_DIR}/samples.txt" | sort >"${RUN_DIR}/expected-filenames.txt"
if [[ -n "$(uniq -d "${RUN_DIR}/expected-filenames.txt")" ]]; then
  echo "ERROR: sample basenames must be unique" >&2
  uniq -d "${RUN_DIR}/expected-filenames.txt" >&2
  exit 2
fi

sample_count="$(wc -l <"${RUN_DIR}/samples.txt" | tr -d ' ')"
if [[ "${sample_count}" -eq 0 ]]; then
  echo "ERROR: no sample messages found" >&2
  exit 2
fi

python3 "${ROOT_DIR}/test/e2e_analyze.py" \
  --samples-file "${RUN_DIR}/samples.txt" \
  --check-samples-only >"${RUN_DIR}/expectations-check.log"

capture_topic() {
  local topic="$1"
  local destination="$2"
  local stderr_file="${destination}.stderr"

  : >"${destination}"
  : >"${stderr_file}"
  oc exec -n "${NAMESPACE}" "${KAFKA_POD}" -- \
    "${KAFKA_CONSUMER}" \
    --bootstrap-server "${KAFKA_BOOTSTRAP}" \
    --topic "${topic}" \
    --from-beginning \
    --timeout-ms "${TOPIC_QUIET_MS}" \
    >"${destination}" 2>"${stderr_file}" || true
}

count_completed_samples() {
  capture_topic outflow "${POLL_DIR}/outflow.jsonl"
  capture_topic review "${POLL_DIR}/review.jsonl"

  {
    jq -Rr 'fromjson? | .filename? // empty' "${POLL_DIR}/outflow.jsonl"
    jq -Rr 'fromjson? | .filename? // empty' "${POLL_DIR}/review.jsonl"
  } | sort -u >"${POLL_DIR}/terminal-filenames.txt"

  comm -12 "${RUN_DIR}/expected-filenames.txt" "${POLL_DIR}/terminal-filenames.txt" \
    | wc -l | tr -d ' '
}

wait_for_terminal_messages() {
  local deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
  local completed
  while true; do
    completed="$(count_completed_samples)"
    echo "    terminal messages: ${completed}/${sample_count}"
    if [[ "${completed}" -eq "${sample_count}" ]]; then
      return 0
    fi
    if [[ $(date +%s) -ge ${deadline} ]]; then
      echo "WARNING: timed out waiting for every message to reach outflow or review" >&2
      return 1
    fi
    sleep "${POLL_SECONDS}"
  done
}

count_expected_sales() {
  capture_topic sales "${POLL_DIR}/sales.jsonl"
  jq -Rr 'fromjson? | .filename? // empty' "${POLL_DIR}/sales.jsonl" \
    | sort -u >"${POLL_DIR}/sales-filenames.txt"
  grep -Ec '^prospect-bulk-order-[12]\.txt$' "${POLL_DIR}/sales-filenames.txt" || true
}

count_review_to_sales_decisions() {
  oc logs -n "${NAMESPACE}" deployment/message-triage-review-to-sales \
    --since-time="${SALES_TEST_STARTED_AT}" 2>/dev/null \
    | grep -Ec 'Review exception (routed to|was not a sales opportunity)' || true
}

wait_for_sales_messages() {
  local deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
  local completed decisions
  while true; do
    completed="$(count_expected_sales)"
    decisions="$(count_review_to_sales_decisions)"
    echo "    sales opportunities: ${completed}/2; review decisions: ${decisions}/${REVIEW_RECORD_COUNT}"
    if [[ "${completed}" -eq 2 && "${decisions}" -ge "${REVIEW_RECORD_COUNT}" ]]; then
      return 0
    fi
    if [[ $(date +%s) -ge ${deadline} ]]; then
      echo "WARNING: timed out waiting for sales output and all review decisions" >&2
      return 1
    fi
    sleep "${POLL_SECONDS}"
  done
}

capture_all_topics() {
  for topic in "${TOPICS[@]}"; do
    echo "    capturing ${topic}"
    capture_topic "${topic}" "${TOPICS_DIR}/${topic}.jsonl"
  done
}

capture_service_logs() {
  for deployment in "${LOG_DEPLOYMENTS[@]}"; do
    if oc get "deployment/${deployment}" -n "${NAMESPACE}" >/dev/null 2>&1; then
      oc logs -n "${NAMESPACE}" "deployment/${deployment}" \
        --since-time="${TEST_STARTED_AT}" \
        >"${LOGS_DIR}/${deployment}.log" 2>&1 || true
    fi
  done
}

echo "==> Verifying the OpenShift demo"
oc get kafka message-triage-kafka -n "${NAMESPACE}" >/dev/null
oc get pod "${KAFKA_POD}" -n "${NAMESPACE}" >/dev/null
oc get route message-triage-http-intake -n "${NAMESPACE}" >/dev/null

trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM

echo "==> Resetting before the test"
"${ROOT_DIR}/openshift/reset-demo.sh" 2>&1 | tee "${RUN_DIR}/reset-before.log"

TEST_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  echo "run_id=${RUN_ID}"
  echo "namespace=${NAMESPACE}"
  echo "started_at=${TEST_STARTED_AT}"
  echo "sample_count=${sample_count}"
  echo "timeout_seconds=${TIMEOUT_SECONDS}"
  echo "poll_seconds=${POLL_SECONDS}"
} >"${RUN_DIR}/run-metadata.txt"
oc get deployments,pods,kafka,kafkatopic -n "${NAMESPACE}" \
  >"${RUN_DIR}/pre-test-state.log" 2>&1

echo "==> Sending all ${sample_count} sample messages"
: >"${RUN_DIR}/submissions.log"
: >"${RUN_DIR}/submission-failures.txt"
while IFS= read -r sample; do
  echo "    ${sample}"
  if ! "${ROOT_DIR}/send.sh" "${sample}" >>"${RUN_DIR}/submissions.log" 2>&1; then
    echo "${sample}" >>"${RUN_DIR}/submission-failures.txt"
    echo "WARNING: submission failed for ${sample}" >&2
  fi
done <"${RUN_DIR}/samples.txt"

echo "==> Waiting for every sample to reach outflow or review"
if [[ -s "${RUN_DIR}/submission-failures.txt" ]]; then
  echo "WARNING: skipping the terminal wait because one or more submissions failed" >&2
else
  wait_for_terminal_messages || true
fi

capture_topic review "${POLL_DIR}/review-before-sales.jsonl"
REVIEW_RECORD_COUNT="$({ jq -Rr 'fromjson? | .filename? // empty' \
  "${POLL_DIR}/review-before-sales.jsonl" || true; } | wc -l | tr -d ' ')"

echo "==> Adding the late review-to-sales agent"
"${ROOT_DIR}/openshift/backend/deploy-review-to-sales.sh" \
  >"${RUN_DIR}/deploy-review-to-sales.log" 2>&1

# A unique group makes the test independent of offsets retained by previous
# demo runs. This Deployment is deleted by the final reset.
SALES_TEST_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
oc set env -n "${NAMESPACE}" deployment/message-triage-review-to-sales \
  KAFKA_OPPORTUNITY_GROUP_ID="message-triage-e2e-${RUN_ID}" \
  >>"${RUN_DIR}/deploy-review-to-sales.log" 2>&1
oc rollout status -n "${NAMESPACE}" deployment/message-triage-review-to-sales \
  --timeout=300s >>"${RUN_DIR}/deploy-review-to-sales.log" 2>&1

echo "==> Waiting for both reviewed sales prospects to reach sales"
if grep -q '^sales/' "${RUN_DIR}/submission-failures.txt"; then
  echo "WARNING: skipping the sales wait because a sales submission failed" >&2
else
  wait_for_sales_messages || true
fi

echo "==> Capturing Kafka records"
capture_all_topics

echo "==> Capturing service logs"
capture_service_logs

echo "==> Validating observed paths"
set +e
python3 "${ROOT_DIR}/test/e2e_analyze.py" \
  --samples-file "${RUN_DIR}/samples.txt" \
  --topics-dir "${TOPICS_DIR}" \
  --output-dir "${RUN_DIR}" \
  --submission-failures "${RUN_DIR}/submission-failures.txt" \
  2>&1 | tee "${RUN_DIR}/analysis.log"
analysis_status=${PIPESTATUS[0]}
set -e

exit "${analysis_status}"
