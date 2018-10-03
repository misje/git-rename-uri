#!/bin/bash
#
# Example script iterating through all git submodules and updating local
# configuration with new URIs.
#
# Copyright © 2018, Andreas Misje

[[ $# -ne 1 ]] && {>&2 echo 'Exactly one argument is expected: A file with a list of .gitmodules paths'; exit 1;}

# Read list of .gitmodules paths into an array:
IFS=$'\n' projects=("$(<$1)")

for project in $projects;do
	path="${project%%.gitmodules}"
	git -C "$path" submodule foreach --recursive 'git submodule sync'
	git -C "$path" submodule sync
done
