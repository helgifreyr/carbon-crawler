#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cygpath -w "$PWD")"

# Registry ports use git@github.com: URLs; fetch them over HTTPS without an SSH key.
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0='url.https://github.com/.insteadOf'
export GIT_CONFIG_VALUE_0='git@github.com:'
export VCPKG_ROOT="$ROOT\\vendor\\vcpkg"
export PATH_TO_VCPKG_ROOT="$VCPKG_ROOT"
export VCPKG_KEEP_ENV_VARS='GIT_CONFIG_COUNT;GIT_CONFIG_KEY_0;GIT_CONFIG_VALUE_0;PATH_TO_VCPKG_ROOT'

./vendor/vcpkg/vcpkg.exe install \
    --triplet x64-windows-v143-internal \
    --host-triplet x64-windows-v143-internal \
    --disable-metrics "$@"
