
#!/usr/bin/python

"""
Checks include dependencies in a cpp project.
"""

from CppHeaderParser import CppHeaderParser
from optparse import OptionParser
from collections import defaultdict
from operator import itemgetter
import os
import re
import sys

class RedirectInputs(object):
    """
    ContextManager for stdout and stderr redirections.
    """
    def __init__(self, stdout, stderr):
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.stdout.flush()
        self.stderr.flush()
        sys.stdout, sys.stderr = self.stdout, self.stderr

    def __exit__(self, *a):
        self.stdout.flush()
        self.stderr.flush()
        sys.stdout, sys.stderr = self.old_stdout, self.old_stderr

def resolve_include(include, include_paths):
    """
    Resolves given include in the context of include prefixes.
    @returns relative path to the include file if it exists
             None otherwise
    """
    stripped = re.sub(r"<(.*)>", r"\1", include)
    for include_prefix in include_paths:
        path = os.path.join(include_prefix, stripped)
        if os.path.exists(path):
            return path

if __name__ == "__main__":
    # parse options
    parser = OptionParser(usage="usage: %prog [options] [include_file]",
                          version="%prog 0.1")
    parser.add_option("-I",
                      "--includes",
                      dest="includes",
                      default=".",
                      help="Space separated list of include paths.")
    parser.add_option("-d",
                      "--num_deps",
                      dest="num_deps",
                      default="10",
                      help="Number of include dependencies to print. Zero means all.")
    parser.add_option("-p",
                      "--num_impacts",
                      dest="num_impacts",
                      default="10",
                      help="Number of include impacts to print. Zero means all.")
    (options, args) = parser.parse_args()
    num_deps = int(options.num_deps)
    num_impacts = int(options.num_impacts)
    include_paths=filter(lambda s: len(s), options.includes.split(" "))
    if len(args) > 1:
        parser.error("Expects at most one argument with file paths.")
    if len(args) == 0 and sys.stdin.isatty():
        parser.error("No input. Expects file paths either on stdin or in a first argument file.")

    if len(args) == 0:
        lines = sys.stdin.readlines()
    else:
        with open(args[0], "r") as f:
            lines = f.readlines()
    # read project files
    filenames = map(lambda s: s.strip(), lines)

    # collect direct include dependencies
    # dependency means that when any of the dependencies is changed the file for which
    # we collect the dependencies (the source) must be recompiled
    # for instance Foo.cpp will depend on Foo.cpp and Foo.hpp
    include_deps = {}
    # parse files for include statements with CppHeaderParser
    # while redirecting any parser output to stderr
    with RedirectInputs(sys.stderr, None):
        for fn in filenames:
            try:
                includes = CppHeaderParser.CppHeader(fn).includes
            except CppHeaderParser.CppParseError:
                continue
            deps = set(filter(lambda res: res != None,
                              map(lambda fn : resolve_include(fn, include_paths),
                                  includes)))
            deps.add(fn)
            include_deps[fn] = deps

    # analyze and enclose the include dependencies
    # this changes the include_deps map in place
    # once we figure that the value of the include dependencies closure can't
    # be expanded we store the filename of the source in finished_sources
    finished_sources = set([])
    while len(finished_sources) != len(include_deps):
        for key, closure in include_deps.items():
            if key in finished_sources:
                continue
            last_len = len(closure)
            for dep in list(closure):
                try:
                    dep_closure = include_deps[dep]
                    closure.update(dep_closure)
                except KeyError:
                    continue
            # closure is finished when last iteration hasn't added anything new
            if len(closure) == last_len:
                finished_sources.add(key)

    # this is the map with inverted relations
    # the value is a set with all files that have the filename in the key
    # as a dependency
    # in other workds: if the key filename changes, all the value filenames have to recompile
    include_impacts = defaultdict(set)
    for key, closure in include_deps.items():
        for dep in closure:
            include_impacts[dep].add(key)

    result_deps = list(reversed(sorted(include_deps.items(),
                                  cmp=lambda fst, snd: cmp(len(fst[1]), len(snd[1])))))
    if num_deps:
        result_deps = result_deps[:num_deps]
    print("Build dependencies:")
    for key, deps in result_deps:
        print("%s %d" % (key, len(deps)))

    result_impacts = list(reversed(sorted(include_impacts.items(),
                              cmp=lambda fst, snd: cmp(len(fst[1]), len(snd[1])))))
    if num_impacts:
        result_impacts = result_impacts[:num_impacts]
    print("")
    print("Impact dependencies:")
    for key, deps in result_impacts:
        print("%s %d" % (key, len(deps)))
