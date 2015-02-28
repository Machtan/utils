import subprocess
import friendlytoml as toml
import sys
import os
import argparse
import shutil

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
        ensure_not_missing("dependencies")
        ensure_not_missing("modules")
        ensure_not_missing("developer")
        ensure_not_missing("authors")
        ensure_not_missing("version")
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
    DEPS = specs['dependencies']
    MODS = specs['modules']
    DEV = specs['developer']
    ASSETS = specs['assets']
    VERSION = specs['version']
    APP_NAME = NAME+".app"
    EXE_NAME = NAME+".exe"
    APP_DIR = pj(BUILD_DIR, APP_NAME)
    ICON_NAME = specs['icon']

    if not os.path.exists(os.path.join(BUILD_DIR, EXE_NAME)):
        return print("Executable not found, cannot bundle.")

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

    exe_path = pj(BUNDLE_DIR, EXE_NAME)
    exe_src = pj(BUILD_DIR, EXE_NAME)
    remove_if_clean(exe_path)
    shutil.copy(exe_src, exe_path)

    # Copy all dlls if this is not a release build
    if not release:
        print("> Copying binaries/assemblies...")
        for dep in DEPS:
            fullname = dep + ".dll"
            dep_src = pj(BINARIES_DIR, fullname)
            dep_dst = pj(BUNDLE_DIR, fullname)
            replace_if_newer(dep_src, dep_dst)

        for mod in MODS:
            fullname = mod + ".dll"
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

    cmd = []
    cmd.append(BUILD_CMD)
    cmd.append("--nologo")

    cmd.append("-I:{}".format(BINARIES_DIR))
    cmd.append("-I:{}".format(BUILD_DIR))

    if platform == "mac":
        cmd.append("-d:TARGET_MAC")

    for dep in specs['dependencies']:
        cmd.append("-r:{}.dll".format(dep))

    # Build the submodules in the right order
    mods = specs['modules']
    submodules = []
    recompile = False
    for mod in mods:
        script = mod + ".fs"
        mod_name = mod + ".dll"
        mod_dst = os.path.join(BUILD_DIR, mod_name)
        if recompile or newer(script, mod_dst):
            print("> Building '{}'...".format(script))
            recompile = True #  Make sure to also recompile the dependent scripts

            # Compile the module
            mod_cmd = cmd + [script, "-a", "-o:{}".format(mod_dst)] + submodules
            print("$ {}".format(" ".join(mod_cmd)))
            exit_status = subprocess.call(mod_cmd)
            if exit_status: #  Interrupt on fail
                print("> Failed to build submodule '{}'".format(mod_name))
                return exit_status
        else:
            print("> '{}' was built, skipping...".format(mod_name))

        submodules.append("-r:{}".format(mod_name))

    # Build the main program
    if release:
        cmd.append("--standalone")

    out_file_name = specs['name'] + EXTENSION
    out_file = os.path.join(BUILD_DIR, out_file_name)
    cmd.append("-o:{}".format(out_file))

    main_file = specs['main']
    cmd.append(main_file)
    cmd.extend(submodules)

    print("$ {}".format(" ".join(cmd)))
    built = subprocess.call(cmd)
    if built: # Exit on failure
        return built

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

    # Compiled version exists
    new_build = force_recompile
    if os.path.exists(target):
        # Check if it needs to be recompiled
        checks = [main_file] + [m + ".fs" for m in specs["modules"]]
        for check in checks:
            if (os.stat(target).st_ctime < os.stat(check).st_ctime):
                print("> New build!")
                new_build = True
                break
    else:
        new_build = True

    if new_build:
        print("> Recompiling...")
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
