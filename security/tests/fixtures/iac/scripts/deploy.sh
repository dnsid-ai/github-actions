#!/usr/bin/env bash
# Self-test target for the IaC workflow.
set -euo pipefail
target=${1:-dev}
# CANARY: shellcheck SC2086, unquoted expansion.
echo deploying to $target
