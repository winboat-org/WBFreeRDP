#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
work_dir=${WBFREERDP_BUILD_DIR:-"$source_dir/build/musl"}
mkdir -p "$work_dir"
work_dir=$(CDPATH= cd -- "$work_dir" && pwd)
engine=${CONTAINER_ENGINE:-}
if [ -z "$engine" ]; then
    if command -v podman >/dev/null 2>&1; then engine=podman; else engine=docker; fi
fi
image=localhost/wbfreerdp-musl-builder:alpine3.23
"$engine" build -f "$source_dir/packaging/musl/Containerfile" -t "$image" "$source_dir/packaging/musl"
if [ "$engine" = podman ]; then
    set -- --userns=keep-id --security-opt label=disable
else
    set --
fi
"$engine" run --rm "$@" --user "$(id -u):$(id -g)" \
    -e "JOBS=${JOBS:-8}" -e XDG_CACHE_HOME=/work/cache \
    -v "$source_dir:/src:ro" -v "$work_dir:/work:rw" "$image"
printf '\nArtifacts: %s/artifacts\n' "$work_dir"
