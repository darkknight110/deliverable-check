#!/usr/bin/env bash
# 负向对照：拿脏表跑。必须非零，且输出里有 FAIL 证据，否则门禁不可信。
set -uo pipefail
python3 scripts/audit_data.py data/dirty.xlsx
