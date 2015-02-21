# Created by Jakob Lautrup Nysom @ February 21st 2015
import subprocess
import argparse
import sys
import os
import shutil
import time
import friendlytoml as toml

config = toml.load(os.path.join(os.path.dirname(__file__), "publish_rust.toml"))

HOME = os.environ["HOME"]
PROJECT_FOLDER = os.path.join(HOME, os.path.join(*config["dir"]["rust"]))
USER = config["user"]
GITHUB_DOMAIN = USER + ".github.io"
GITHUB_FOLDER = os.path.join(HOME, os.path.join(*config["dir"]["github"]), GITHUB_DOMAIN)

def publish(PROJECT, UPDATE=False):
    """Attempts to publish the rust project at the given path"""
    path = os.path.join(PROJECT_FOLDER, PROJECT)
    if not os.path.exists(path):
        return print("Could not find project directory: '{}'".format(path))

    if UPDATE:
        print("> Force Update: ON")
    
    if not os.path.exists(GITHUB_FOLDER):
        print("Github repo not found, creating at '{}'...", GITHUB_FOLDER)
        os.makedirs(GITHUB_FOLDER)
    
    def prompt(msg):
        """Helper function for simple prompts"""
        confirmations = {"y", "yes", "yup", "yea", "sure", "indeed"}
        if UPDATE: 
            return True
        else:
            print("> ", end="")
            res = input(msg+" (y/n)\n>>> ").lower()
            return res in confirmations
    
    CARGO_PATH = os.path.join(path, "Cargo.toml")
    cargo = toml.load(CARGO_PATH)
    package = cargo["package"]
    
    CRATE = package["name"]
    AUTHORS = package["authors"]
    AUTHOR_STRING = AUTHORS[0] if len(AUTHORS) == 1 else ", ".join(AUTHORS)
    
    REPOSITORY = "https://github.com/" + USER + "/" + PROJECT
    DOCUMENTATION = "https://" + GITHUB_DOMAIN + "/" + PROJECT + "/" + CRATE
    
    LICENSE_FILE = config["license"]["file"]
    LICENSE_PATH = os.path.join(path, LICENSE_FILE)
    LICENSE_SHORT = config["license"]["short"]
    
    README_FILE = config["readme"]["file"]
    README_PATH = os.path.join(path, README_FILE)
    
    TRAVIS_FILE = config["travis"]["file"]
    TRAVIS_PATH = os.path.join(path, TRAVIS_FILE)
    TRAVIS_URL = "https://travis-ci.org/" + USER + "/" + PROJECT
    
    os.chdir(path)
    print("> Preparing publishment")

    print("> Building...")
    res = subprocess.call(["cargo", "build"])
    if res: return print("> Error while building")

    print("> Testing...")
    res = subprocess.call(["cargo", "test"])
    if res: return print("> Error while testing")

    print("> Compiling documentation...")
    res = subprocess.call(["cargo", "doc"])
    if res: return print("> Error while compiling documentation")
    
    # Travis CI
    if not os.path.exists(TRAVIS_PATH) or UPDATE:
        print("> Adding '{}'...".format(TRAVIS_FILE))
        travis_template = config["travis"]["template"]
        with open(TRAVIS_PATH, "w") as f:
            f.write(travis_template)
    
    # License
    if (not os.path.exists(LICENSE_PATH)) or UPDATE:
        print("> Adding '{}' license at '{}'...".format(LICENSE_SHORT, LICENSE_PATH))
        license_map = {
            "author": AUTHOR_STRING, 
            "year": time.localtime().tm_year
        }
        license = config["license"]["long"].format_map(
            license_map)
        with open(LICENSE_PATH, "w") as f:
            f.write(license)
    
    # github.io Documentation
    source = os.path.join(path, "target", "doc")
    destination = os.path.join(GITHUB_FOLDER, PROJECT)
    if os.path.exists(destination) and prompt("Update documentation?"):
        print("> Cleaning destination folder...")
        shutil.rmtree(destination)
    
    if not os.path.exists(destination):
        print("> Moving new documentation files...")
        shutil.copytree(source, destination)
    
    # Readme
    if not os.path.exists(README_PATH) or prompt("Overwrite existing README?"):
        print("> Writing README at '{}'...".format(README_PATH))
        readme_map = {
            "project": PROJECT,
            "license_short": LICENSE_SHORT,
            "documentation_url": DOCUMENTATION,
            "repository": REPOSITORY,
            "crate": CRATE,
            "travis_url": TRAVIS_URL
        }
        readme = config["readme"]["template"].format_map(readme_map)
        with open(README_PATH, "w") as f:
            f.write(readme)
    
    # Crates.io cargo metadata
    cargo_updated = []
    def find_or_set(key, default):
        if (not key in package) or UPDATE:
            package[key] = default
            cargo_updated.append(True)
    
    find_or_set("readme", README_FILE)
    find_or_set("documentation", DOCUMENTATION)
    find_or_set("license", LICENSE_SHORT)
    
    if cargo_updated:
        print("> Updating cargo metadata...")
        with open(CARGO_PATH, "w") as f:
            toml.dump(cargo, f)

    print("> Done! Added to '{}'".format(destination))

def main(args=sys.argv[1:]):
    """Entry point"""
    parser = argparse.ArgumentParser()

    parser.add_argument("project",
        help="The name of the folder of the rust project to publish")
    parser.add_argument("-f", "--force_update", action="store_true", default=False,
        help="Forces everything to be updated/overwritten by default")

    parsed = parser.parse_args()
    publish(parsed.project, UPDATE=parsed.force_update)

if __name__ == '__main__':
    main()
