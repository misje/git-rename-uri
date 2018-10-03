# git-rename-uri
Utility to recursively rename (remote) URIs in git projects

git-rename-uri expects a JSON file containing search paramaters and a
substitution dictionary. A simple example:

``` json
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
```

With this file search for .git/config files recursively and replace all
occurrences matching the provided search rules and replace the URLs.
.gitmodules can also be modified.

(Note that search.hostname and search.path are regular expressions, which have
to be escaped to be valid JSON. These expressions are part of a bigger
expression and must not contain anchors like '^' and '$'.)

git-rename-uri provides several ways to test your rules before changing your files.
In all cases git-rename-uri expects a JSON file as the first argument and one or
several files or directories. The files are expected to be .git/config files
(and/or .gitmodules files if --modules is given) and/or directories that will
be searched recursively for mentioned files.

`git-rename-uri --list-configs`

  Simply list all the .git/config files found (with matching URIs inside)

`git-rename-uri --list-projects`

  List all the project names matching the search criteria. If the project does
  not have a substitution rule, a warning will be issued.

`git-rename-uri --list-projects --list-categorised --show-new-path`

  List all found projects, indented by config file name, along with the new
  name it will be substituted with (not the full URI, but the new path).

`git-rename-uri --dry-run`

  Print the contents of all the files that would have been modified.

The resulting URI must be specified with hostname, username and protocol. All
of these can be overridden by the command line.

TIP: Before changing .gitmodules files, it might be a good idea to run `git-rename-uri
--list-config --modules-only` to get a list of the modified projects. This can
be handy for an automated script running 'git commit' of the changes later:
    `git-rename-uri --list-config config.json --modules-only my_path`

This is done by the helper script 'list_affected_gitmodules.sh'. Another
script, commit_gitmodules_changes.sh, will add and commit all affected
.gitmodules files and push them to the remote 'origin'. The complete list of
actions for renaming all URIs in local .git/configs as well as updating all
submodules and committing and pushing the changes are as follows:

 1. Do a dry run first:
 `git-rename-uri --modules --dry-run config.json my_paths`
 1. Store a list of the projects that will be changed and needs to be commited:
 `/usr/share/doc/git-rename-uri/scripts/list_affected_gitmodules.sh config.json my_paths > modified_projects`
 1. Replace URIs:
 `git-rename-uri --modules config.json my_paths`
 1. Add, commit and push changes to submodule URIs:
 `/usr/share/doc/git-rename-uri/scripts/commit_gitmodules_changes.sh modified_projects`
