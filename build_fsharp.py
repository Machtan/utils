import subprocess
import friendlytoml as toml
import sys
import os
import argparse
import shutil

from depres import resolve_build_order

"""
An F# MonoGame build utility
Very tightly coupled atm.
"""

CONFIG = "fargo.toml"
BUILD_CMD = "fsharpc"
EXTENSION = ".exe"
BUILD_DIR = "target"
BIN_DIR = "MacOS"
BINARIES_DIR = "binaries"
LAUNCHER = "MonoMacLauncher"

class SpecException(Exception):
    """An exception for spec errors"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def get_build_command(graph, target, prefix="", includes=[], library=True, 
        extra_flags=[]):
    """Creates the fsharp build command for the given item"""
    cmd = ["fsharpc", "--nologo", target + ".fs"]
    suffix = ".exe"
    if library:
        cmd.append("-a")
        suffix = ".dll"
    for inc in includes:
        cmd.append("-I:{}".format(inc))
    for dep in graph[target][1]:
        cmd.append("-r:{}.dll".format(dep))
    if prefix:
        cmd.append("-o:{}{}".format(os.path.join(prefix, target), suffix))
    cmd.extend(extra_flags)
    return cmd

def load_spec():
    """Attempts to load the local build specification"""
    if not os.path.exists(CONFIG):
        raise SpecException("Config file not found: Please create" +
            " '{}' in your project directory".format(CONFIG))
    else:
        spec = toml.load(CONFIG)

        missing = []
        def ensure_not_missing(key):
            if not key in spec:
                missing.append(key)

        # Validate some shit
        ensure_not_missing("name")
        ensure_not_missing("main")
        ensure_not_missing("assets")
        ensure_not_missing("targets")
        ensure_not_missing("developer")
        ensure_not_missing("authors")
        ensure_not_missing("version")
        ensure_not_missing("libraries")
        ensure_not_missing("icon")
        if missing:
            print("The following fields were missing!")
            print("- "+"\n- ".join(missing))
            raise Exception("Bad build file, missing fields.")
        else:
            return spec

def newer(src, dst):
    """Returns whether the first path is newer than the second"""
    if not os.path.exists(dst):
        return True
    else:
        return os.stat(src).st_ctime > os.stat(dst).st_ctime

def replace_if_newer(source, destination):
    """Replaces the file at destination with the file at source if the source is newer"""
    if newer(source, destination):
        if os.path.exists(destination):
            os.remove(destination)
        shutil.copy(source, destination)

def ensure_build():
    if not os.path.exists(BUILD_DIR):
        os.makedirs(BUILD_DIR)

def bundle(clean=False, release=False):
    """Bundles the target as a mac application"""
    def remove_if_clean(path):
        if clean and os.path.exists(path):
            os.remove(path)

    def ensure_dir(path):
        if not os.path.exists(path):
            os.mkdir(path)

    # For the love of god
    pj = os.path.join

    specs = load_spec()
    AUTHORS = specs['authors']
    NAME = specs['name']
    MAIN = specs['main']
    LIBS = specs['libraries']
    TARGETS = specs['targets']
    DEV = specs['developer']
    ASSETS = specs['assets']
    VERSION = specs['version']
    APP_NAME = NAME + ".app"
    EXE_NAME = MAIN + ".exe"
    APP_DIR = pj(BUILD_DIR, APP_NAME)
    ICON_NAME = specs['icon']

    if not os.path.exists(os.path.join(BUILD_DIR, EXE_NAME)):
        print("Executable not found, cannot bundle.")
        return 1

    # Begin!
    print("> Bundling app...")
    ensure_dir(APP_DIR)

    # Create the contents dir
    CONTENTS_DIR = pj(APP_DIR, "Contents")
    ensure_dir(CONTENTS_DIR)

    # Create the plist
    print("> Writing Property List...")
    with open("plist_template.txt", "r") as f:
        template = f.read()
    plist_map = {
        "name": NAME,
        "bundle_identifier": DEV + "." + NAME,
        "version_short": VERSION,
        "icon_name": ICON_NAME,
        "authors": ", ".join(AUTHORS)
    }
    plist = template.format_map(plist_map)
    plist_path = pj(CONTENTS_DIR, "Info.plist")
    remove_if_clean(plist_path)
    with open(plist_path, "w") as f:
        f.write(plist)

    # Create the binary dir
    print("> Adding launcher...")
    LAUNCHER_DIR = pj(CONTENTS_DIR, "MacOS")
    ensure_dir(LAUNCHER_DIR)
    launcher_path = pj(LAUNCHER_DIR, NAME)
    #remove_if_clean(launcher_path)
    if not os.path.exists(launcher_path):
        for file in os.listdir(LAUNCHER_DIR): #  Remove old launchers
            if not file.startswith("."):
                os.remove(pj(LAUNCHER_DIR, file))
        launcher_src = pj(BINARIES_DIR, LAUNCHER)
        shutil.copy(launcher_src, launcher_path)

    # Move the executable and dependencies
    print("> Adding binaries and assemblies... (.exe and .dll)")
    BUNDLE_DIR = pj(CONTENTS_DIR, "MonoBundle")
    ensure_dir(BUNDLE_DIR)
    for file in os.listdir(BUNDLE_DIR): #  Remove the old exe
        if file.endswith(".exe"):
            os.remove(pj(BUNDLE_DIR, file))

    exe_dst = pj(BUNDLE_DIR, NAME + ".exe")
    exe_src = pj(BUILD_DIR, EXE_NAME)
    remove_if_clean(exe_dst)
    shutil.copy(exe_src, exe_dst)

    # Copy all dlls if this is not a release build
    if not release:
        print("> Copying binaries/assemblies...")
        for dep in LIBS:
            fullname = dep + ".dll"
            dep_src = pj(BINARIES_DIR, fullname)
            dep_dst = pj(BUNDLE_DIR, fullname)
            replace_if_newer(dep_src, dep_dst)

        for target in TARGETS:
            if target == MAIN:
                continue
            fullname = target + ".dll"
            mod_src = pj(BUILD_DIR, fullname)
            mod_dst = pj(BUNDLE_DIR, fullname)
            replace_if_newer(mod_src, mod_dst)

    # Move the Assets
    print("> Adding assets...")
    RES_DIR = pj(CONTENTS_DIR, "Resources")
    ensure_dir(RES_DIR)
    icon_dst = pj(RES_DIR, ICON_NAME)
    icon_src = ICON_NAME
    replace_if_newer(icon_src, icon_dst)

    ensure_dir(pj(RES_DIR, os.path.basename(ASSETS)))
    for dirpath, dirnames, filenames in os.walk(ASSETS):
        for dirname in dirnames:
            if dirname.startswith("."):
                continue
            dir_dst = pj(dirpath, dirname)
            print(">>> dir_dst: {}".format(dir_dst))
            ensure_dir(dir_dst)
        for filename in filenames:
            if filename.startswith("."):
                continue
            file_src = pj(dirpath, filename)
            file_dst = pj(RES_DIR, dirpath, filename)
            print(">>> file: src/dst '{}' / '{}'".format(file_src, file_dst))
            replace_if_newer(file_src, file_dst)

    print("> Done!")
    print("> Saved to '{}'".format(APP_DIR))

def build(platform="mac", release=False):
    """Builds the F# program from the given specification dictionary"""
    specs = load_spec()
    ensure_build()
    
    TARGETS = specs['targets']
    LIBS = specs["libraries"]
    MAIN = specs["main"]
    
    INCLUDES = [BINARIES_DIR, BUILD_DIR]
    EXTRA_FLAGS = [] 
    if platform == "mac":
        EXTRA_FLAGS.append("-d:TARGET_MAC")
    if release:
        EXTRA_FLAGS.append("-O")
    PREFIX = BUILD_DIR
    
    # Resolve dependencies
    # - Populate the graph
    graph = {}
    for library in LIBS:
        graph[library] = (False, [])
        
    for target, deps in TARGETS.items():
        suffix = ".exe" if target == MAIN else ".dll"
        src = target + ".fs"
        dst = os.path.join(BUILD_DIR, target + suffix)
        updated = newer(src, dst)
        graph[target] = (updated, deps)
    
    # Get the build order
    order = resolve_build_order(graph, MAIN)
    
    # Exit early if the build is not needed
    needs_rebuild = False
    for t, n in order:
        if n:
            needs_rebuild = True
            break
    if not needs_rebuild:
        return 0
    
    #print("Order:")
    #print(order)
    
    for target, needs_build in order:
        if needs_build:
            extra = EXTRA_FLAGS
            if target == MAIN:
                lib = False
                if release:
                    extra.append("--standalone")
            else:
                lib = True
            print("> Building '{}'...".format(target))
            cmd = get_build_command(graph, target, prefix=PREFIX, 
                includes=INCLUDES, library=lib, extra_flags=extra)
            print("$ {}".format(" ".join(cmd)))
            exit_status = subprocess.call(cmd)
            if exit_status: #  Interrupt on fail
                print("> Failed to build '{}'".format(target))
                return exit_status
        else:
            print("> '{}' was built, skipping...".format(target))

    # Bundle the program if on mac
    if platform == "mac":
        bundled = bundle()
        return bundled
    else:
        return built

def run(force_recompile=False, args=[]):
    """Builds if necessary, then runs the current project"""
    specs = load_spec()
    NAME = specs['name']
    target = os.path.join(BUILD_DIR, NAME + EXTENSION)
    main_file = specs['main']

    if build(): # Return not 0 => error
        return print("Error while building! Run failed.")

    RUN_PATH = os.path.join(BUILD_DIR, NAME+".app", "Contents", BIN_DIR, NAME)
    cmd = [RUN_PATH] + args
    print("> Running...")
    print("$ {}".format(" ".join(cmd)))
    try:
        result = subprocess.call(cmd)
        return result
    except KeyboardInterrupt as e:
        print("\n> Interrupted!")
        return 1

def clean():
    """Cleans the build directory"""
    for dirpath, dirnames, filenames in os.walk(BUILD_DIR):
        for dirname in dirnames:
            if dirname.endswith(".app"):
                shutil.rmtree(os.path.join(dirpath, dirname))
        for filename in filenames:
            if not filename.startswith("."):
                os.remove(os.path.join(dirpath, filename))
    print("> All clean!")

def main(args=sys.argv[1:]):
    """Entry point"""
    # Prepare
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title = "commands")

    build_desc = "Builds the project executable"
    build_parser = subparsers.add_parser("build", description=build_desc)
    build_parser.set_defaults(func=build)

    run_desc = "Builds and runs the project executable"
    run_parser = subparsers.add_parser("run", description=run_desc)
    run_parser.add_argument("-f", "--force_recompile",
        action="store_true", default=False,
        help="Forces the program to recompile before running")
    run_parser.add_argument("args", nargs="*", default=[],
        help="Arguments for the executable")
    run_parser.set_defaults(func=run)

    bundle_desc = "Bundles the project"
    bundle_parser = subparsers.add_parser("bundle", description=bundle_desc)
    bundle_parser.set_defaults(func=bundle)

    clean_desc = "Cleans the target directory"
    clean_parser = subparsers.add_parser("clean", description=clean_desc)
    clean_parser.set_defaults(func=clean)

    # Parse
    parsed = parser.parse_args()

    # Run
    if not hasattr(parsed, "func"):
        parser.print_usage()
    else:
        try:
            func = parsed.func
            del(parsed.func)
            func(**vars(parsed))
        except SpecException as e:
            print("! Error loading build file:\n{}".format(e))

if __name__ == '__main__':
    main()
