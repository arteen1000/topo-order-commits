import os
import sys
import zlib


class CommitObject:
    def __init__(self, commit_hash):
        """
        used to represent commits

        ordering made deterministic by using [] instead of set()
        based on underlying filesystems output of contents

        checked by running looped version of:
        $ comm -3 <(python3 topo_order_commits.py) <(python3 topo_order_commits.py)
        and comparing list of CommitObjects
        """

        self.commit_hash = commit_hash
        self.parents = []
        self.children = []
        self.temp_parents = []

    def __repr__(self):
        return f'commit_hash: {self.commit_hash} parent(s): {self.parents} children: {self.children}\n'

    def __eq__(self, other):
        return other == self.commit_hash

    def initialize_temp_parents(self):
        self.temp_parents[:] = self.parents


def navigate_to_git_parent_directory():
    """
    traverse to the parent directory of .git

    return with process in parent directory of .git
    """

    while not os.path.exists('.git'):

        if os.getcwd() == '/':
            print('Not inside a Git Repository',
                  file=sys.stderr)
            sys.exit(1)

        os.chdir('..')


def return_branches():
    """
    return a dict of hashes with a corresponding
    list of associated branchnames

    return with process in .git directory
    """

    if not os.path.isdir('.git'):
        print('.git is not a directory',
              file=sys.stderr)
        sys.exit(1)

    os.chdir('.git')

    if not os.path.isdir('refs/heads'):
        print('.git is not a valid Git Repository',
              file=sys.stderr)
        sys.exit(1)

    os.chdir('refs/heads')

    branches = {}

    # recursively walk the file hierarchy starting at ('.')
    for current, subs, files in os.walk('.'):
        for filename in files:

            # os.walk does not change cwd
            # ignores . and ..
            
            # ./path/to/filename -> path/to/filename from cwd
            path = os.path.join(current, filename)[2:]
            
            
            with open(path, 'r') as fd:
                sha1_hash = fd.readline().strip() # remove \n
                if branches.get(sha1_hash) is None:
                    branches[sha1_hash] = [path]
                else:
                    branches[sha1_hash].append(path)

    os.chdir('../..')
    
    if not branches:
        print('no branches found in .git/refs/heads',
              file=sys.stderr)
        sys.exit(1)
    
    return branches


def grab_commits():
    """
    assume start in .git

    return list of CommitObject(s) with all loose commits
    in .git repository filled along with their parents
    
    process returns in .git/objects directory
    """

    if not os.path.isdir('objects'):
        print('.git is not a valid Git Repository',
              file=sys.stderr)
        sys.exit(1)

    os.chdir('objects')

    commits = []

    for current, subs, files in os.walk('.'):

        # can prune the search to exclude info/ and pack/
        # assuming no pack-files

        # issue if branches in info/ pack/
        # subs[:] = [s for s in subs if s not in ['info', 'pack']]

        # print(f'{current} {subs} {files}')

        for filename in files:

            # './##/#{38}' -> '##/#{38}'
            path = os.path.join(current, filename)[2:]

            with open(path, 'rb') as fd:

                # reads raw bytes from file descriptor

                data = zlib.decompress(fd.read())  # read and decompress binary data

                # http://git-scm.com/book/en/v2/Git-Internals-Git-Objects
                # every object has header and content, git cat-file shows content

                header, content = data.split(b'\0', 1)

                # content format:
                # tree <sha1>
                # parent <sha1>
                # parent <sha1>
                # ...
                # author (end of parents)

                # assuming UTF-8 encoding (default) vs. legacy
                # https://git-scm.com/docs/git-commit#_discussion
                # .decode() also defaults to utf-8

                if header.startswith(b'commit'):
                    commit = CommitObject(path.replace('/', ''))  # commit hash
                    for line in content.split(b'\n'):
                        if line.startswith(b'author'):
                            break
                        elif line.startswith(b'parent'):
                            line = line.decode()
                            commit.parents.append(line[7:])  # parent hash
                    commits.append(commit)

    if not commits:
        print('Could not find any commits, may be packed or nonexistent',
              file=sys.stderr)
        sys.exit(1)

    return commits


def grab_corresponding_commit(commits, commit_object_or_hash):
    for commit in commits:
        if commit == commit_object_or_hash:
            return commit
    return None


def remove_unvisited_commits(commits, visited):
    for commit in commits:
        if commit not in visited:
            commits.remove(commit)


def build_commit_graph(branches, commits, root_commits):
    """
    return with commits being
    list of CommitObjects s.t.
    
    1. commits unreachable from branch heads
    are not included
    2. all commits children are included
    """
    
    visited = {}  # commit : visited_status
    processing_list = []

    for branch_hash in branches:
        processing_list.append(branch_hash)

    # only visit those reachable from the branch hashes

    for commit_hash in processing_list:
        if visited.get(commit_hash) is True:  # visited
            continue
        else:
            visited[commit_hash] = True  # visit

        # print(commits)
        # print(hash)
        commit = grab_corresponding_commit(commits, commit_hash)
        # print (commit)
        if not commit.parents:  # empty
            root_commits.append(commit_hash)

        for parent in commit.parents:
            if visited.get(parent) is None:
                processing_list.append(parent)
                visited[parent] = False

            parent_commit = grab_corresponding_commit(commits, parent)
            parent_commit.children.append(commit_hash)

    visited = list(visited)  # those that should be kept
    remove_unvisited_commits(commits, visited)  # unreachables


def topological_sort(commits, root_commits):
    """
    return a topologically sorted list
    of commit hashes
    """
    
    sorted_list = []
    processing_list = root_commits  # no copy necessary, won't use again

    for commit in commits:
        commit.initialize_temp_parents()  # avoid overwriting parents

    for commit_hash in processing_list:
        sorted_list.append(commit_hash)
        commit = grab_corresponding_commit(commits, commit_hash)
        for child in commit.children:
            child_commit = grab_corresponding_commit(commits, child)
            try:
                child_commit.temp_parents.remove(commit_hash)
            except ValueError:
                print('attempting to remove nonexisting parent',
                      file=sys.stderr)
            if not child_commit.temp_parents:  # empty
                processing_list.append(child)

    for commit in commits:
        if commit.temp_parents:
            print('cycle in .git graph detected', file=sys.stderr)
            sys.exit(1)

    if len(commits) != len(sorted_list):
        print('failure to generate topological sort', file=sys.stderr)
        sys.exit(1)

    return sorted_list

    # for every one to be processed (start with root)
    #  add it to the sorted_list
    #  for all its children
    #    remove itself as a parent
    #    if they have no parents now
    #      add them to the processing_list
    #


def print_sticky_sorted_order(topo_ordered_commits, commits, branches):
    """
    print out commits s.t.

    C
    <parents of C>=
    <empty line>
    when next to be printed is not parent of C

    =<children of C>
    C
    if previous line was <empty line>
    """
    
    prev_empty = False
    for current_hash, next_hash in zip(topo_ordered_commits, topo_ordered_commits[1:] + [None]):

        current_commit = grab_corresponding_commit(commits, current_hash)

        if prev_empty:
            print("=", end="")
            print(*current_commit.children)
            prev_empty = False

        if branches.get(current_hash) is None:
            print(current_hash)
        else:
            print(current_hash, *branches[current_hash])

        if next_hash is not None and next_hash not in current_commit.parents:
            print(*current_commit.parents, end="")
            print("=\n")
            prev_empty = True

        # if prev is empty line
        #  print =children of current hash
        #  prev_empty = false

        # print current hash with branches

        # if next commit to be printed is not parent of current
        #  print parents of current=
        #  print empty line
        #  prev_empty = true


def topo_order_commits():
    # 1. discover the .git directory

    navigate_to_git_parent_directory()

    # 2. get the list of local branch names and corresponding commits

    branches = return_branches()

    # 3. build the commit graph
    
    commits = grab_commits()

    # len() > 1 if git checkout --orphan or manual manipulation
    root_commits = []
    
    # print(commits)
    # print(branches)
    build_commit_graph(branches, commits, root_commits)

    # 4. topological sort

    topo_ordered_commits = topological_sort(commits, root_commits)
    # tested determinicitiy by comm -23 <(...) <(...)

    topo_ordered_commits.reverse()  # descendants first
    for branch in branches:
        branches[branch].sort()  # lexicographical order branch names

    # 5. print sticky sorted order

    print_sticky_sorted_order(topo_ordered_commits, commits, branches)

    # 6. verify with strace

    # strace -f -o topo-test.tr pytest
    # [ $(grep -c execve topo-test.tr) -eq 1 ]
    # echo $?
    # [ $(strace -f python3 topo_order_commits.py 2>&1 | grep -c execve) -eq 1 ]
    # echo $?

if __name__ == '__main__':
    topo_order_commits()

