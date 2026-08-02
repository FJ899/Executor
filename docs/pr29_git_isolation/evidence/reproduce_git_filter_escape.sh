#!/bin/sh
set -eu

ROOT=${1:-/tmp/executor-git-filter-repro}
rm -rf "$ROOT"
mkdir -p "$ROOT/source/project_registry" "$ROOT/bin"
cd "$ROOT/source"

git init -q
git config user.name tester
git config user.email tester@example.invalid
printf 'BROKEN\n' > project_registry/registry.py
git add project_registry/registry.py
git commit -qm initial

cat > "$ROOT/bin/filter.sh" <<'EOF'
#!/bin/sh
printf '%s\n' "$FILTER_PHASE" >> "$FILTER_MARKER"
cat
EOF
chmod +x "$ROOT/bin/filter.sh"

# Neither .git/info/attributes nor .git/config dirties the tracked checkout.
printf 'project_registry/registry.py filter=hostexec\n' > .git/info/attributes
git config filter.hostexec.smudge "$ROOT/bin/filter.sh"
git config filter.hostexec.clean "$ROOT/bin/filter.sh"

export FILTER_MARKER="$ROOT/filter-marker"
export FILTER_PHASE=smudge

printf 'source_status_before=%s\n' "$(git status --porcelain --untracked-files=all)"

# These are the same safety overrides used by executor/pilot_core.py::git_command.
git -C "$ROOT/source" \
  -c core.hooksPath=/dev/null \
  -c core.fsmonitor=false \
  -c core.attributesFile=/dev/null \
  -c core.autocrlf=false \
  -c commit.gpgSign=false \
  worktree add --detach "$ROOT/worktree" HEAD >/dev/null

if [ -f "$FILTER_MARKER" ]; then
  echo 'smudge_via_git_info_attributes=EXECUTED'
else
  echo 'smudge_via_git_info_attributes=NOT_EXECUTED'
fi

export FILTER_PHASE=clean
printf 'FIXED\n' > "$ROOT/worktree/project_registry/registry.py"
git -C "$ROOT/worktree" \
  -c core.hooksPath=/dev/null \
  -c core.fsmonitor=false \
  -c core.attributesFile=/dev/null \
  -c core.autocrlf=false \
  -c commit.gpgSign=false \
  add -- project_registry/registry.py >/dev/null

if grep -q '^clean$' "$FILTER_MARKER"; then
  echo 'clean_via_git_info_attributes=EXECUTED'
else
  echo 'clean_via_git_info_attributes=NOT_EXECUTED'
fi

printf 'source_status_after=%s\n' "$(git -C "$ROOT/source" status --porcelain --untracked-files=all)"
printf 'source_head=%s\n' "$(git -C "$ROOT/source" rev-parse HEAD)"
printf 'worktree_head=%s\n' "$(git -C "$ROOT/worktree" rev-parse HEAD)"
printf 'git_version=%s\n' "$(git --version)"
echo 'marker_contents:'
cat "$FILTER_MARKER"
