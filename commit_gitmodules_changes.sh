#!/bin/bash
#
# Example script showing how to possibly add and commit changes done by
# git-rename-uri to projects and submodules.
#
# Copyright © 2018, Andreas Misje

[[ $# -ne 1 ]] && {>&2 echo 'Exactly one argument is expected: A file with a list of .gitmodules paths'; exit 1;}
set -e
set -o pipefail
set -o nounset

# Read list of .gitmodules paths into an array:
IFS=$'\n' projects=("$(<$1)")
# Submodule commit message (if not provided as environment variable):
: ${SUBCOMMITMSG:='Update URIs in submodule'}
# Commit message (if not provided as environment variable):
: ${COMMITMSG:='Use submodule with updated URI'}
# Name of branch to switch to if it exists:
: ${BRANCH:=''}
: ${FALLBACKBRANCH:='master'}
# Name of remote (if not provided as environment variable):
: ${REMOTE:='origin'}

checkout() {
	local path="$1"
	local branch="$BRANCH"
	if [[ "$BRANCH" ]]; then
		# Check if requested branch exists:
		if ! git -C "$path" show-ref --verify --quiet refs/heads/"$BRANCH"; then
			# Fall back to master (to avoid commiting on detached HEAD):
			branch="$FALLBACKBRANCH"
		fi
		git -C "$path" checkout "$branch"
	else
		2>/dev/null git symbolic-ref HEAD || {>&2 echo "$path: HEAD is detached"; exit 1;}
	fi
}

perform_changes() {
	local path="$1"
	local file="$2"
	local commit_msg="$3"
	# Checkout a spesific branch, if required:
	checkout "$path"
	git -C "$path" add "$file"
	git -C "$path" commit -m "$commit_msg" || true
	git -C "$path" fetch "$REMOTE"
	# Use tracked upstream if it exists:
	local upstream=$(git -C "$path" for-each-ref --format='%(upstream:short)' $(git -C "$path" symbolic-ref -q HEAD))
	# Otherwise guess "$REMOTE/HEAD":
	: ${upstream:="$REMOTE/$(git -C "$path" rev-parse --abbrev-ref HEAD)"}
	git -C "$path" rebase "$upstream"
	git -C "$path" push "$REMOTE" HEAD
}

set -x

# Commit all changes to .gitmodules:
for project in $projects;do
	# Extract path by removing '.gitmodules' from the name:
	path="${project%%.gitmodules}"

	perform_changes "$path" .gitmodules "$SUBCOMMITMSG"
done

# For nested gitmodules, also add and commit the now updated submodules (with
# new URIs):
declare -A updated_projects
for project in $projects;do
	# Extract path by removing '.gitmodules' from the name:
	path="${project%%.gitmodules}"

	# If inside submodule:
	if [[ $(git -C "$path" rev-parse --show-superproject-working-tree) ]]; then
	  parent="$(dirname -- "$path")"
	  # Add and commit reference to updated submodule, but only once:
	  # FIXME: Allow 'git add' several time, but only do one commit:
	  #if [[ ${updated_projects["$parent"]+exists} ]]; then
	  #   continue
	  #fi
	  subproj="$(basename -- "$path")"
	  perform_changes "$parent" "$subproj" "$COMMITMSG"
	  updated_projects["$parent"]=1
  fi
done
