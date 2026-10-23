#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo 'Usage: bash scripts/apply-patch.sh STRATA_SOURCE' >&2
  exit 2
fi
package=$(cd "$(dirname "$0")/.." && pwd)
source_root=$(cd "$1" && pwd)
expected=011c9e600a93bbc9fd451c563501b5831c32bbca
test "$(git -C "$source_root" rev-parse HEAD)" = "$expected" || {
  echo 'Expected the exact Strata v0.2.2 commit; use a separate clean checkout.' >&2
  exit 1
}
test -z "$(git -C "$source_root" status --porcelain --untracked-files=normal)" || {
  echo 'Source checkout has changes; preserve them and use a clean checkout.' >&2
  exit 1
}
git -C "$source_root" apply --check "$package/patches/strata-v0.2.2-gfx1100.patch"
git -C "$source_root" apply "$package/patches/strata-v0.2.2-gfx1100.patch"
echo 'Applied FP16 select + structured-tools patch, including the select parity test.'
