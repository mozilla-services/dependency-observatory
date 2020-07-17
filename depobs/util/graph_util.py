import logging
from typing import (
    AbstractSet,
    Any,
    Dict,
    Iterable,
    List,
    Tuple,
    TypeVar,
    Set,
    Union,
    Optional,
)

import graphviz
import networkx as nx

from depobs.database import models
from depobs.models.nodejs import NPMPackage
from depobs.models.rust import RustCrate, RustPackageID, RustPackage

T = TypeVar("T")

log = logging.getLogger(__name__)


NODE_ID_FORMATS = {
    "name": "{pkg_id.name}",
    "name_version": "{pkg_id.name} {pkg_id.version}",
    "name_version_source": "{pkg_id.name} {pkg_id.version} {pkg_id.source}",
    "source": "{pkg_id.source}",
}

NODE_LABEL_FORMATS = {
    "name": "{crate.package_id.name}",
    "name_version": "{crate.package_id.name} {crate.package_id.version}",
    "name_version_source": "{crate.package_id.name} {crate.package_id.version} {crate.package_id.source}",
    "source": "{crate.package_id.source}",
    "name_authors": "{crate.package_id.name}\n{crate_package.authors}",
    "name_readme": "{crate.package_id.name}\n{crate_package.readme}",
    "name_repository": "{crate.package_id.name}\n{crate_package.repository}",
    "name_version_repository": "{crate.package_id.name} {crate.package_id.version}\n{crate_package.repository}",
    "name_license": "{crate.package_id.name}\n{crate_package.license}",
    "name_package_source": "{crate.package_id.name}\n{crate_package.source}",
    "name_metadata": "{crate.package_id.name}\n{crate_package.metadata}",
}

GROUP_ATTRS = {
    "author": lambda node: node[1]["crate_package"].authors or [],
    "repository": lambda node: node[1]["crate_package"].repository or "",
    # 'workspace':
    # 'manifest_path':
    # 'source_repository':
}


def npm_packages_to_networkx_digraph(packages: Iterable[NPMPackage]) -> nx.DiGraph:
    g = nx.DiGraph()
    for package in packages:
        node_id = package.package_id
        g.add_node(node_id, label=node_id)
        for dep_id in package.dependencies:
            g.add_edge(node_id, dep_id)
    return g


def rust_crates_and_packages_to_networkx_digraph(
    args: Any,  # TODO: define TypedDict for graphing display options
    crates_and_packages: Tuple[Dict[str, RustCrate], Dict[str, RustPackage]],
) -> nx.DiGraph:
    log.debug(f"graphing with args: {args}")
    crates, packages = crates_and_packages

    node_id_format = NODE_ID_FORMATS[args.node_key]
    node_label_format = NODE_LABEL_FORMATS[args.node_label]

    g = nx.DiGraph()
    for c in crates.values():
        node_id = node_id_format.format(pkg_id=c.package_id)

        g.add_node(
            node_id,
            label=node_label_format.format(crate=c, crate_package=packages[c.id]),
            crate=c,
            crate_package=packages[c.id],
        )
        for dep in c.deps:
            dep_id = node_id_format.format(pkg_id=RustPackageID.parse(dep["pkg"]))
            g.add_edge(
                node_id,
                dep_id,
                # name=dep["name"],
                # features=dep["features"],
            )

    return g


def get_authors(g: nx.DiGraph) -> Set[str]:
    return {
        author
        for (nid, n) in g.nodes(data=True)
        for author in n["crate_package"].authors or []
        if author
    }


def get_repos(g: nx.DiGraph) -> Set[str]:
    return {n["crate_package"].repository for (nid, n) in g.nodes(data=True)}


def has_changes(result: Dict) -> bool:
    for k, v in result.items():
        if not isinstance(v, dict):
            continue
        if "new" in v:
            if len(v["new"]):
                return True
        if "old" in v:
            if len(v["removed"]):
                return True
    return False


def get_new_removed_and_new_total(
    lset: AbstractSet[T], rset: AbstractSet[T]
) -> Tuple[AbstractSet[T], AbstractSet[T], int]:
    new = rset - lset
    removed = lset - rset
    new_total = len(rset)
    return new, removed, new_total


def get_graph_stats(g: nx.DiGraph) -> Dict[str, Union[int, bool, List[int], List[str]]]:
    stats = dict(
        node_count=g.number_of_nodes(),
        edge_count=g.number_of_edges(),
        # zero (no edges) to one (complete / all nodes directly linked to each other)
        density=nx.density(g),
        # list index is the degree count, value is the number of nodes with that degree (# of adjacent nodes)
        degree_histograph=nx.classes.function.degree_histogram(g),  # List[int]
        is_dag=nx.algorithms.dag.is_directed_acyclic_graph(g),  # bool
    )

    if stats["is_dag"]:
        # longest/deepest path through the DAG
        stats["longest_path"] = nx.algorithms.dag.dag_longest_path(g)  # List[str]
        stats["longest_path_length"] = len(stats["longest_path"])
    else:
        stats["cycle"] = list(nx.find_cycle(g))

    # number of edges pointing to a node
    stats["average_in_degree"] = sum(d for n, d in g.in_degree()) / float(
        stats["node_count"]
    )

    # number of edges a node points to
    stats["average_out_degree"] = sum(d for n, d in g.out_degree()) / float(
        stats["node_count"]
    )
    # NB: avg in and out degrees should be equal

    return stats


def package_graph_to_networkx_graph(db_graph: models.PackageGraph) -> nx.DiGraph:
    """
    Converts a DB PackageGraph model into a networkx.DiGraph
    """
    g = nx.DiGraph(incoming_graph_data=None, id=db_graph.id)

    for (
        link_id,
        (parent_package_id, child_package_id),
    ) in db_graph.package_links_by_id.items():
        if parent_package_id == child_package_id:
            log.warning(f"skipping self loop for package version ID {child_package_id}")
            continue

        g.add_edge(parent_package_id, child_package_id, link_id=link_id)
    g.add_nodes_from(db_graph.distinct_package_ids)
    return g


def update_node_attrs(
    g: nx.DiGraph, **updates_by_package_version_id: Dict[int, Any]
) -> None:
    """
    Updates or replaces node attributes for nodes in a nx.DiGraph.

    Takes a dict of updates
    using the node id.

    e.g.

    >>> update_node_attrs(nx.DiGraph([(0, 1)]), label={0: 'node 0'}).nodes[0]['label']
    'node 0'
    >>> update_node_attrs(nx.DiGraph([(0, 1)]), label={0: 'node 0'}, foo={0: 'bar'}).nodes[0]
    {'label': 'node 0', 'foo': 'bar'}
    """
    for attr_name, node_id_to_value in updates_by_package_version_id.items():
        for node_id, attr_value in node_id_to_value.items():
            g.nodes[node_id][attr_name] = attr_value

    return g


def nx_digraph_to_graphviz_digraph(
    g: nx.DiGraph, dot_graph: Optional[graphviz.Digraph] = None,
) -> graphviz.Digraph:
    """
    Adds nodes and dedges from a networkx DiGraph to a graphviz

    Digraph (Yes, graph in DiGraph is capitalized for nx but not for
    graphviz). Creating a new graphviz Digraph if necessary.
    """
    if dot_graph is None:
        dot_graph = graphviz.Digraph()

    for node_id, node_data in g.nodes(data=True):
        dot_graph.node(
            str(node_id),
            label=node_data["label"] if node_data and "label" in node_data else None,
        )

    for src, dest, data in g.edges(data=True):
        dot_graph.edge(str(src), str(dest))

    return dot_graph
