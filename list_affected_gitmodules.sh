#!/bin/bash
#
# Example script listing (to be) modified git projects in a sorted order.
#
# Copyright © 2018, Andreas Misje

set -e
config="${1:-config.json}"
path="${2:-.}"
# List all .gitmodules files that will be modified, sorted by longest path in a
# reverse order (in order to iterate the submodules inside-out):
./git-rename-uri.py --list-config "$config" --modules-only "$path" | awk '{ print length($0) " " $0; }' | sort -r -n | cut -d ' ' -f 2-
