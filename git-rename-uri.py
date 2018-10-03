#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Utility to rename (remote) URIs in git projects.
#
# Copyright © 2018, Andreas Misje

import glob
import argparse
import re
import os.path
import shutil
import sys
import tempfile
import itertools
import json

VALID_PROTOCOLS = ['git', 'ssh', 'http', 'https', 'ssh-colon', 'file', 'relative']
VERSION = '0.1.0'

parser = argparse.ArgumentParser(
        description = 'Recursively search directory for .git/config files and update all remote URIs',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = '''
%(prog)s expects a JSON file containing search paramaters and a substitution
dictionary. A simple example:

{
  "search": {
     "hostname": "oldgit|oldgit.example.org",
     "path": "/+(?:var|srv)/+git"
   },
  "replace": {
    "hostname": "newgit.example.com",
    "username": "git",
    "protocol": "ssh-colon",
    "substitutions": {
      "oldproject1": "new/path/project1",
      "oldproject2": "oldproject2"
    }
  }
}

With this file search for .git/config files recursively and replace all
occurrences matching the provided search rules and replace the URLs.
.gitmodules can also be modified.

(Note that search.hostname and search.path are regular expressions, which have
to be escaped to be valid JSON. These expressions are part of a bigger
expression and must not contain anchors like '^' and '$'.)

%(prog)s provides several ways to test your rules before changing your files.
In all cases %(prog)s expects a JSON file as the first argument and one or
several files or directories. The files are expected to be .git/config files
(and/or .gitmodules files if --modules is given) and/or directories that will
be searched recursively for mentioned files.

%(prog)s --list-configs
  Simply list all the .git/config files found (with matching URIs inside)

%(prog)s --list-projects
  List all the project names matching the search criteria. If the project does
  not have a substitution rule, a warning will be issued.

%(prog)s --list-projects --list-categorised --show-new-path
  List all found projects, indented by config file name, along with the new
  name it will be substituted with (not the full URI, but the new path).

%(prog)s --dry-run
  Print the contents of all the files that would have been modified.

The resulting URI must be specified with hostname, username and protocol. All
of these can be overridden by the command line. When using the protocol
'relative' the hostname may be of the form '../..' and username is ignored.

TIP: Before changing .gitmodules files, it might be a good idea to run %(prog)s
--list-config --modules-only to get a list of the modified projects. This can
be handy for an automated script running 'git commit' of the changes later:
    %(prog)s --list-config config.json --modules-only my_path

This is done by the helper script 'list_affected_gitmodules.sh'. Another
script, commit_gitmodules_changes.sh, will add and commit all affected
.gitmodules files and push them to the remote 'origin'. The complete list of
actions for renaming all URIs in local .git/configs as well as updating all
submodules and committing and pushing the changes are as follows:
    # Do a dry run first:
    %(prog)s --modules --dry-run config.json my_paths
    # Store a list of the projects that will be changed and needs to be commited:
    /usr/share/doc/%(prog)s/scripts/list_affected_gitmodules.sh config.json my_paths > modified_projects
    # Replace URIs:
    %(prog)s --modules config.json my_paths
    # Add, commit and push changes to submodule URIs:
    /usr/share/doc/%(prog)s/scripts/commit_gitmodules_changes.sh modified_projects
        '''
        )
parser.add_argument('--list-configs', action = 'store_true', help = 'List all matching .git/config files and do nothing else')
parser.add_argument('--list-projects', action = 'store_true', help = 'List all projects found in all found .git/config files and do nothing else')
parser.add_argument('--show-new-path', const = ' → ', default = None, nargs = '?', help = 'When listing projects, also show their new paths, separated by a delimiter (default " → ")')
parser.add_argument('--list-categorised', action = 'store_true', help = 'When listing projects, print them indented under the config file they are found in')
parser.add_argument('--dry-run', '-d', action = 'store_true', help = 'Instead of substituting paths just print what would have been done (same as --list-projects --show-new-path --list-categorised')
parser.add_argument('--protocol', '-p', choices = VALID_PROTOCOLS, help = 'Protocol to use in the new URI, default ssh (overrides config)')
parser.add_argument('--username', '-u', help = 'Username to use in the new URI (overrides config)')
parser.add_argument('--modules', '-m', action = 'store_true', help = 'Replace/inspect URIs in .gitmodules files as well')
parser.add_argument('--modules-only', action = 'store_true', help = 'Replace/inspect URIs in .gitmodules files only')
parser.add_argument('--hostname', help = 'Hostname in the new URI (overrides config)')
parser.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
parser.add_argument('config', help = 'JSON configuration file')
parser.add_argument('targets', nargs = '+', metavar = 'file|directory', help = 'One or several directories containing git projects, or one or several git project files, to be updated')

def printIfMatching(gitConfigFile):
    with open(gitConfigFile, 'r') as config:
        if regex.search(config.read()):
            print(gitConfigFile)

def listProjects(gitConfigFile, subst, categorise = False, showNew = None):
    if categorise:
        print(gitConfigFile, ':', sep='')

    with open(gitConfigFile, 'r') as config:
        for match in regex.finditer(config.read()):
            project = match.group('project')
            try:
                newName = subst[project]
            except KeyError :
                print('WARNING: The project "{0}" does not have a defined new path'.format(project), file = sys.stderr)
                continue

            if categorise:
                print('\t', end='')
            if showNew is not None:
                print('{0}{1}{2}'.format(project, showNew, newName))
            else:
                print(match.group('project'))

def replace(gitConfigFile, subst, host, proto, username = None, dryRun = False):
    if dryRun:
        print('In {0} the following would be the new contents:'.format(gitConfigFile))

    (_, tempFile) = tempfile.mkstemp()
    try:
        with open(gitConfigFile, 'r') as configOrig, open(tempFile, 'w') as temp:
            def replace(match):
                project = match.group('project')
                try:
                    newName = subst[project]
                except KeyError :
                    print('WARNING: The project "{0}" does not have a defined new path and will not be replaced'.format(project), file = sys.stderr)
                    if not dryRun:
                        temp.write(match.string)

                    return match.string

                user = username + '@' if username is not None else ''
                if proto == 'ssh-colon':
                    uri = '{user}{host}:{path}'.format(
                        user = user,
                        host = host,
                        path = newName
                        )
                elif proto == 'relative':
                    uri = '{host}/{path}'.format(
                            host = host,
                            path = newName
                            )
                else:
                    uri = '{proto}://{user}{host}/{path}'.format(
                        proto = proto,
                        user = user,
                        host = host,
                        path = newName
                        )

                return match.group('key') + uri

            result = regex.sub(lambda match: replace(match), configOrig.read())
            if dryRun:
                print(result)
            else:
                temp.write(result)

    except IOError as e:
        print('Failed to replace config / creating temporary file {}: {}'.format(e.filename, e.strerror), file = sys.stderr)
        try:
            os.remove(tempFile)
        except IOError:
            pass
    else:
        if not dryRun:
            shutil.move(tempFile, gitConfigFile)

def confFiles(path, includeGitModules = False, gitModulesOnly = False):
    if gitModulesOnly:
        return glob.iglob(target + '/**/.gitmodules', recursive = True)
    elif includeGitModules:
        return itertools.chain(
                glob.iglob(target + '/**/.git/config', recursive = True),
                glob.iglob(target + '/**/.git/modules/**/config', recursive = True),
                glob.iglob(target + '/**/.gitmodules', recursive = True)
                )
    else:
        return itertools.chain(
                glob.iglob(target + '/**/.git/config', recursive = True),
                glob.iglob(target + '/**/.git/modules/**/config', recursive = True)
                )

def validateJSONConfig(json):
    if 'protocol' in json['replace'] and json['replace']['protocol'] not in VALID_PROTOCOLS:
        raise ValueError('replace/protocol "{}" is invalid (valid protocols: {})'
                .format(json['replace']['protocol'], ', '.join(VALID_PROTOCOLS)))

    try:
        re.compile(json['search']['hostname'])
        re.compile(json['search']['path'])
    except re.error as e:
        print('Config contains invalid regex "{}": {}'.format(e.pattern, e.msg), file = sys.stderr)

if __name__ == '__main__':
    args = parser.parse_args()

    with open(args.config) as confFile:
        json = json.load(confFile)

    validateJSONConfig(json)

    regex = re.compile("""
    ^(?P<key>\s*url\s*=\s*)
    (?:
    # Either an URI:
      (?:(file|ssh|git|http|https)://)?         # protocol, optional
      (?:[a-z_][a-z0-9_-]*[$]?@)??              # Linux username, followed by '@', optional
      (?:{hosts})                               # Accepted hostnames
      :?(?:{paths})                             # Common paths
    | # or a relative path
      \.\.)
    /+(?P<project>[^\.\n]+)                     # project name
    (?:\.git)??                                 # optionally followed by ".git"
    \s*$""".format(
        hosts = json['search']['hostname'],
        paths = json['search']['path']), re.MULTILINE | re.VERBOSE)

    for target in args.targets:
        if os.path.isdir(target):
            for config in confFiles(target, args.modules, args.modules_only):
                if args.list_configs:
                    printIfMatching(config)
                elif args.list_projects:
                    listProjects(
                            config,
                            subst = json['replace']['substitutions'],
                            categorise = args.list_categorised,
                            showNew = args.show_new_path
                            )
                else:
                    replace(
                            config,
                            subst = json['replace']['substitutions'],
                            host = args.hostname if args.hostname else json['replace']['hostname'],
                            proto = args.protocol if args.protocol else json['replace']['protocol'],
                            username = args.username if args.username else json['replace'].get('username'),
                            dryRun = args.dry_run
                            )
        else:
            if args.list_configs:
                printIfMatching(target)
            elif args.list_projects:
                listProjects(
                        target,
                        subst = json['replace']['substitutions'],
                        categorise = args.list_categorised,
                        showNew = args.show_new_path
                        )
            else:
                    replace(
                            target,
                            subst = json['replace']['substitutions'],
                            host = args.hostname if args.hostname else json['replace']['hostname'],
                            proto = args.protocol if args.protocol else json['replace']['protocol'],
                            username = args.username if args.username else json['replace'].get('username'),
                            dryRun = args.dry_run
                            )
