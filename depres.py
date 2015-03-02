
import os
import friendlytoml as toml

"""
Simple dependency resolution utility
"""

def resolve_build_order(graph, target):
    """Resolves the build rules for the build dependency graph.
    Returns the order in which things should be built, and whether they should be 
    built or not as a list of (name, needs_build) tuples"""
    accumulator = []
    visited = set()
    def resolve_internal(graph, target, acc, vis):
        #print("Checking {}...".format(target))
        updated, deps = graph[target]
        for n, dep in enumerate(deps):
            #print("- dep {}: {}".format(n, dep))
            result = resolve_internal(graph, dep, acc, vis)
            updated = updated or result
            
        if not target in vis:
            acc.append((target, updated))
            vis.add(target)
        return updated
        
    resolve_internal(graph, target, accumulator, visited)
    return accumulator

def main():
    """Entry point (Simple testing)"""
    graph = {
        "MonoGame":     (0, []),
        "Program":      (0, ["CarGame"]),
        "CarGame":      (0, ["MonoGame", "CarInput", "CarActor", "CarPhysics"]),
        "CarActor":     (0, ["MonoGame"]),
        "CarInput":     (0, ["MonoGame", "CarActor"]),
        "CarPhysics":   (1, ["MonoGame", "CarActor"]),
    }
    target = "Program" 
    
    PREFIX = "target"
    INCLUDES = ["binaries", "target"]
    
    order = resolve_build_order(graph, target)
    print("Build rules:")
    for item, build in order:
        print("- {}: {}".format(item, bool(build)))

if __name__ == '__main__':
    main()