#!/usr/bin/env bash
# 交付前数据体检：0 = 可交付；1 = 有阻断（未通过就不许发）
set -euo pipefail
exec python3 scripts/audit_data.py "${1:-data/clean.xlsx}"
