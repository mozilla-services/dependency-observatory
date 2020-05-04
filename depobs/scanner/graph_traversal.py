from typing import (
    Generator,
    Iterable,
    Optional,
    Set,
    Tuple,
)

import networkx as nx
from networkx.algorithms.components import condensation
from networkx.algorithms.dag import descendants, is_directed_acyclic_graph
from networkx.algorithms.shortest_paths.generic import has_path

# type alias to not confuse ints as nxGraphNodeIDs with other ints
nxGraphNodeID = int


def outer_in_graph_iter(
    g: nx.DiGraph, c: Optional[nx.DiGraph] = None
) -> Generator[Set[nxGraphNodeID], None, None]:
    """For a directed graph with unique node IDs with type int, iterates
    from outer / leafmost / least depended upon nodes to inner nodes
    yielding sets of node IDs. Optionally, takes a precomputed condensed
    DAG of g.

    Properties:

    * yields each node ID once
    * successive node ID sets only depend on/point to previously visited
    nodes or other nodes within their set
    """
    if len(g.nodes) == 0:
        raise StopIteration("graph has no nodes")

    # > C – The condensation graph C of G. The node labels are integers
    # > corresponding to the index of the component in the list of strongly
    # > connected components of G. C has a graph attribute named ‘mapping’ with
    # > a dictionary mapping the original nodes to the nodes in C to which they
    # > belong. Each node in C also has a node attribute ‘members’ with the set
    # > of original nodes in G that form the SCC that the node in C represents.
    #
    # https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.condensation.html#networkx.algorithms.components.condensation
    if not c:
        c = condensation(g)
    assert is_directed_acyclic_graph(c)
    for scc_ids in outer_in_dag_iter(c):
        yield scc_ids_to_graph_node_ids(c, scc_ids)


def outer_in_dag_iter(g: nx.DiGraph) -> Generator[Set[nxGraphNodeID], None, None]:
    """
    For a DAG with unique node IDs with type int, iterates from outer
    / leafmost / least depended upon nodes to inner nodes yielding sets
    of node IDs.

    Yields each node ID once and visits them such that successive node ID sets
    only depend on/point to previously visited nodes.
    """
    if len(g.nodes) == 0:
        raise StopIteration("graph has no nodes")
    if len(g.nodes) > 1 and not is_directed_acyclic_graph(g):
        raise Exception("graph has more than one node and is not a DAG")

    visited: Set[nxGraphNodeID] = set()
    leaf_nodes: Set[nxGraphNodeID] = set(
        [node for node in g.nodes() if g.out_degree(node) == 0]
    )
    yield leaf_nodes
    visited.update(leaf_nodes)

    while True:
        points_to_visited = set(src for (src, _) in g.in_edges(visited))
        only_points_to_visited = set(
            node
            for node in points_to_visited
            if all(dst in visited for (_, dst) in g.out_edges(node))
        )
        new_only_points_to_visited = only_points_to_visited - visited
        if not bool(new_only_points_to_visited):  # visited nothing new
            assert len(visited) == len(g.nodes)
            break
        yield new_only_points_to_visited
        visited.update(only_points_to_visited)


def scc_ids_to_graph_node_ids(c: nx.DiGraph, scc_ids: Iterable[int]):
    # translate scc node ids back into G node ids
    g_node_ids: Set[nxGraphNodeID] = set()
    g_node_ids.update(*[c.nodes[scc_id]["members"] for scc_id in scc_ids])
    return g_node_ids


def node_dep_ids_iter(
    g: nx.DiGraph, c: Optional[nx.DiGraph] = None
) -> Generator[nxGraphNodeID, Set[nxGraphNodeID], Set[nxGraphNodeID]]:
    """For a directed graph with unique node IDs with type int and
    optional precomputed condensed DAG of g, iterates over sets of
    strongly connected components from outer / leafmost / least depended
    upon nodes to inner nodes.

    For each set of strongly connected components, yield each node by
    decreasing ID with its sets of immediate or direct dependencies
    (path length one) and transitive or indirect dependencies (path
    length greater than one).

    Properties:

    * yields each node ID once
    * successive node IDs only depend on/point to previously visited
    nodes or other nodes within their set?

    >>>

    """
    # TODO: rewrite indirect_dep_ids as <visited / descendants from the condensed graph> + <nodes in gray zone / to score area>

    visited: Set[int] = set()
    for node_ids in outer_in_graph_iter(g, c):
        for node_id in sorted(node_ids, reverse=True):
            direct_dep_ids: Set[int] = set(g.successors(node_id))
            indirect_dep_ids: Set[int] = set(
                [
                    dest_id
                    for dest_id in (visited | node_ids)
                    if has_path(g, node_id, dest_id)
                ]
            ) - direct_dep_ids - set([node_id])

            yield node_id, direct_dep_ids, indirect_dep_ids

        visited.update(node_ids)
