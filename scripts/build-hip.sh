#!/usr/bin/env bash
# A separate engine and CPU vision build; never overwrites an installed engine.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  echo 'Usage: bash scripts/build-hip.sh STRATA_SOURCE LLAMA_CPP_SOURCE ROCM_ROOT' >&2
  exit 2
fi
source_root=$(cd "$1" && pwd)
llama_root=$(cd "$2" && pwd)
sdk=$(cd "$3" && pwd)
package=$(cd "$(dirname "$0")/.." && pwd)
test "$(git -C "$source_root" rev-parse HEAD)" = 011c9e600a93bbc9fd451c563501b5831c32bbca
test "$(git -C "$llama_root" rev-parse HEAD)" = 3cf03257f219afbe7334045ff7c6a06ac68c627d
test -z "$(git -C "$llama_root" status --porcelain --untracked-files=normal)"
test -f "$source_root/src/kernels/qsa_select_wmma_parity.cpp"
git -C "$source_root" apply --reverse --check "$package/patches/strata-v0.2.2-gfx1100.patch"
test -x "$sdk/llvm/bin/clang++"
test -d "$sdk/lib/llvm/amdgcn/bitcode"
test -f "$sdk/include/rocwmma/rocwmma.hpp"
for directory in "$source_root/build-gfx1100" "$source_root/build-vision"; do
  test ! -e "$directory" || { echo "Use fresh build directories: $directory" >&2; exit 1; }
done
export LD_LIBRARY_PATH="$sdk/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ROCM_PATH="$sdk" HIP_PATH="$sdk"
cmake -S "$source_root" -B "$source_root/build-gfx1100" \
  -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF \
  -DCMAKE_HIP_ARCHITECTURES=gfx1100 -DCMAKE_HIP_COMPILER="$sdk/llvm/bin/clang++" \
  -DCMAKE_HIP_COMPILER_ROCM_ROOT="$sdk" -DCMAKE_PREFIX_PATH="$sdk" \
  "-DCMAKE_HIP_FLAGS=--rocm-path=$sdk --rocm-device-lib-path=$sdk/lib/llvm/amdgcn/bitcode" \
  -DSTRATA_GGML_DIR="$llama_root" -DSTRATA_BUILD_TESTS=ON
cmake --build "$source_root/build-gfx1100" --target strata strata-device \
  qsa_scores_gfx1100_parity qsa_select_wmma_parity hip_prompt_attn_wmma \
  -j"${STRATA_BUILD_JOBS:-6}"
cmake -S "$source_root/tools/vision" -B "$source_root/build-vision" \
  -DCMAKE_BUILD_TYPE=Release -DLLAMA_DIR="$llama_root" \
  -DSTRATA_VISION_CUDA=OFF -DSTRATA_VISION_HIP=OFF -DSTRATA_PORTABLE=OFF
cmake --build "$source_root/build-vision" --target strata-vision -j"${STRATA_BUILD_JOBS:-6}"
sha256sum "$source_root/build-gfx1100/strata" "$source_root/build-vision/bin/strata-vision"
