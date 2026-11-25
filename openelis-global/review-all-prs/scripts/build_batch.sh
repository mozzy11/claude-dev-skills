#!/bin/sh
# build_batch.sh <ref-name> <pr>... : merge PR heads onto upstream/develop with merge-tree, no checkout
set -u
R=/Users/mosesmutesasira/Desktop/DEV/Projects/OpenELIS/develop/OpenELIS-Global-2
NAME=$1; shift
git -C $R fetch -q upstream develop
HEAD=$(git -C $R rev-parse upstream/develop)
for n in "$@"; do
  git -C $R fetch -q upstream "+pull/$n/head:pr-$n" || { echo "$n FETCH-FAIL"; continue; }
  OUT=$(git -C $R merge-tree --write-tree "$HEAD" "pr-$n" 2>&1)
  if [ $? -ne 0 ]; then
    echo "$n CONFLICT $(printf '%s\n' "$OUT" | grep -E '^CONFLICT' | head -3 | tr '\n' ' ')"
    continue
  fi
  TREE=$(printf '%s\n' "$OUT" | head -1)
  HEAD=$(git -C $R commit-tree "$TREE" -p "$HEAD" -p "pr-$n" -m "batch + pr-$n")
  echo "$n ok $(git -C $R rev-parse --short pr-$n)"
done
git -C $R update-ref "refs/review/$NAME" "$HEAD"
echo "refs/review/$NAME = $HEAD"
