Splay tree
- nearly balanced BST
  - Always splay node after operation (move it up to the root bc you accessed it last, adjust accordingly)
  - Amortized logn per operation

Centrality
- How "important" a node is

------------------------------

### Effects of adding/removing a package on total number of installed package versions
- Number of packages in dependency graph for new package - (packages existing dep. graph ∩ packages in new dep. graph)
  - Upper bounded by # of direct + transitive dependencies of the new package, lower bounded by 1 (package has no dependencies or all of its dependencies are already installed)
  - Include names of new packages

### Effects of adding/removing a package on number of unique trusted maintainers
- Number of unique maintainers in dependency graph for new package - number of unique maintainers in the intersection of new dependency graph and existing dependency graph
  - Upper bounded by the unique number of maintainers direct + transitive dependencies of the new package, lower bounded by 0 (already have packages by maintainers in new package + dependencies)
  - Include names/emails of new maintainers

### If I want to distrust a package, how hard will it be to remove / not install the package?

We can calculate the number of dependencies (direct and transitive) we need to remove by starting at the node in the package constraint graph and traversing "backwards" up the graph until we reach the root, counting the number of unique "ancestors".

For the example above, this would mean A has 1 dependent (application), B and C both have 2 (application and A) and D has 4 (application, A, B and C). This number would represent the "hardness" of removing the package.

### If I want to distrust a package maintainer, how hard will it be to remove their packages?

You could use the same measurements as above to aggregate the total number of dependencies you would have to break to remove all packages in the tree made by a certain maintainer.

----

#### Other ideas
- Somehow incorporate a "popularity" rating for a package/maintainer in terms of the whole NPM ecosystem. This could tell you how hard a package/maintainer would be to avoid in the ecosystem in addition to in your own project.
  - For packages this could be based on the number of dependent packages (how likely it would appear as a dependency of something else you install)
  - For maintainers this could be based on the number of packages they are maintainers on multiplied by dependents per package (how likely they would appear ad one of the maintainers for a dependency of something else you install)
