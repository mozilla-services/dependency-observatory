# npm

## General

### [Packages vs Modules](https://docs.npmjs.com/about-packages-and-modules)

- The npm registry contains packages, many of which are also Node modules, or contain Node modules.

#### Packages
- A package is a file or directory that is described by a `package.json` file
  - a) A folder containing a program described by a package.json file.
  - b) A gzipped tarball containing (a).
  - c) A URL that resolves to (b).
  - d) A `<name>@<version>` that is published on the registry with (c).
  - e) A `<name>@<tag>` that points to (d).
  - f) A `<name>` that has a latest tag satisfying (e).
  - g) A git url that, when cloned, results in (a).

#### Modules
- A module is any file or directory in the `node_modules` directory that can be loaded by the Node.js `require()` function.
  - A folder with a `package.json` file containing a "main" field.
  - A folder with an `index.js` file in it.
  - A JavaScript file.

### [Shrinkwrap]()

## [Install Algorithm](https://docs.npmjs.com/cli/install#algorithm)

```
load the existing node_modules tree from disk
clone the tree
fetch the package.json and assorted metadata and add it to the clone
walk the clone and add any missing dependencies
  dependencies will be added as close to the top as is possible
  without breaking any other modules
compare the original tree with the cloned tree and make a list of
actions to take to convert one to the other
execute all of the actions, deepest first
  kinds of actions are install, update, remove and move
```
- Algorithm is deterministic, but you may get different trees if different packages are installed in a different order (e.g. installing an older version of a dependency first and then needing to also install a newer version after).
- There is an edge case where you can get cyclic dependencies
  - e.g. `A -> B -> A' -> B' -> A -> B -> A' -> B' -> A -> ...` where A and A' are two versions of the same package (ditto for B and B')
  - To deal with this, `npm` refuses to install any `package@version` that already exists in the tree of package ancestors

## [Arborist Deep Dive](https://blog.npmjs.org/post/618653678433435649/npm-v7-series-arborist-deep-dive)

- > A big part of the job of a package manager is to take a set of declarations about dependency constraints, find a graph that solves the constraints, and then reify that graph onto disk such that the resulting program will load the right things.
- Representing the dependency graph as a tree resulted in walking the tree multiple times within one call of a command
  - This was a result of `optionalDependencies` and other similar types of dependencies
- Arborist denotes each node in the dependency set with the `Node` class, and relationships between notes with the `Edge` class
  - The `Node` objects have `edgesOut` (things it depends on) and `edgesIn` (things that depend on it) properties
  - `Node`s also have `children` (contents of the node's `node_modules` folder) and `parent` (reference to the node with this node as a child) properties
  - `Edge` objects have a `from` node, a `to` node, a `type`, a `spec`, and some information about whether the relationship is currently met or not.
  - This means that you can avoid doing multiple tree walks
  - Whenever `parent` is changed, everything is automatically updated (all edges, `children`, etc)
- > Rather than treat the lockfile as a one-off data structure to be consulted at the beginning and serialized back out at the end, Arborist has a Shrinkwrap class that is kept continually up to date as nodes are moved around in the tree.
- Inventory of Nodes in a Project
  - The `root` node, which represents the main project, contains an `Inventory`, which allows you to access all the nodes in the project
- Tree Building Algorithm
  - Maximal naive deduplication: starts at a node, queues a list of dependencies that are missing/invalid. It then goes through the queue, and for each module in `node_modules`, walks up the tree to find the shallowest placement for it. The module itself is then added to the queue so its dependencies can be satsfied.
  - [Build Ideal Tree](https://github.com/npm/arborist/blob/master/notes/ideal-tree.md)

## [Package Signing](https://docs.npmjs.com/about-pgp-signatures-for-packages-in-the-public-registry)

- Add PGP signature to package metadata
- PGP keys are on Keybase
