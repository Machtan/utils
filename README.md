# Utilities
These are just a random assortment of utility python scripts.

Right now, only newer things are added here, but I might migrate some older stuff in the future.

# License
MIT (Do what you want!)

# Descriptions
Short descriptions of what each script does and requires. I'll try to have these be alphabetical.


## publish_rust.py
### About
Just created so that I won't have to manage as much, when a rust crate is close to publishable.
It builds, tests and compiles documentation, adds license and travis files, creates a templated README, updates the cargo metadata with these new things, and moves the created documentation to the github.io repository for later committing.

Everything important should be tweakable using publish_rust.toml, so please make sure that you don't try and publish to my repos or create a load of folders in wrong places :3.

### Use
It's a commandline script

```
python3 publish_rust.py --help
```

### Dependencies
*[Python 3.2+](https://www.python.org/downloads/)*

*[Machtan/friendlytoml](https://github.com/machtan/friendlytoml)*

Currently it uses my own 'friendlytoml' for TOML handling, but any python toml library would do, you'll just have to change the file like this:

```python
#import friendlytoml as toml
import toml
```

*publish_rust.toml*

This is the configuration file. You'll need it.

