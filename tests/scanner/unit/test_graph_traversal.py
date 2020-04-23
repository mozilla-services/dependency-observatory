# -*- coding: utf-8 -*-

import pytest

import depobs.scanner.graph_traversal as m


outer_in_iter_failing_testcases = {
    "no_nodes_no_edges": m.nx.empty_graph(n=0, create_using=m.nx.DiGraph),
    "self_loop": (m.nx.DiGraph([(0, 0)]), [set([0])],),
    "two_node_loop": m.nx.DiGraph([(0, 1), (1, 0)]),
    "three_node_loop": m.nx.DiGraph([(0, 1), (1, 2), (2, 0)]),
    "two_two_node_loops": m.nx.DiGraph([(0, 1), (1, 0), (0, 2), (2, 0)]),
    "nested_three_and_two_node_loops": m.nx.DiGraph(
        [(0, 1), (1, 2), (2, 0), (0, 1), (1, 0), (0, 2), (2, 0)]
    ),
}


@pytest.mark.parametrize(
    "bad_graph, expected_exception",
    [(g, Exception) for g in outer_in_iter_failing_testcases.values()],
    ids=outer_in_iter_failing_testcases.keys(),
)
def test_outer_in_iter_bad_input(bad_graph, expected_exception):
    with pytest.raises(expected_exception):
        next(m.outer_in_iter(bad_graph))


outer_in_iter_testcases = {
    "one_node_no_edges": (m.nx.trivial_graph(create_using=m.nx.DiGraph), [set([0])],),
    "five_node_path_graph": (
        m.nx.path_graph(5, create_using=m.nx.DiGraph),
        [set([i]) for i in range(4, -1, -1)],
    ),
    "small_tree": (
        m.nx.DiGraph([(0, 1), (1, 2), (1, 3), (1, 4), (2, 4)]),
        [set([3, 4]), set([2]), set([1]), set([0])],
    ),
}


@pytest.mark.parametrize(
    "graph, expected_nodes",
    outer_in_iter_testcases.values(),
    ids=outer_in_iter_testcases.keys(),
)
def test_outer_in_iter(graph, expected_nodes):
    nodes = list(m.outer_in_iter(graph))
    # visits all nodes
    assert set(graph.nodes()) == set().union(*nodes)

    # visits each node once
    for node_set in nodes:
        assert all(
            node_set.isdisjoint(other_node_set)
            for other_node_set in nodes
            if other_node_set != node_set
        )

    # only visits node when its deps were already visited
    visited = set()
    for node_set in nodes:
        for node in node_set:
            assert all(dst in visited for (_, dst) in graph.out_edges(node))
        visited |= node_set

    # returns expected values
    assert nodes == expected_nodes
    assert len(nodes) == len(expected_nodes)


outer_in_graph_iter_failing_testcases = {
    "no_nodes_no_edges": m.nx.empty_graph(n=0, create_using=m.nx.DiGraph),
}


@pytest.mark.parametrize(
    "bad_graph, expected_exception",
    [(g, Exception) for g in outer_in_graph_iter_failing_testcases.values()],
    ids=outer_in_graph_iter_failing_testcases.keys(),
)
def test_outer_in_graph_iter_bad_input(bad_graph, expected_exception):
    with pytest.raises(expected_exception):
        next(m.outer_in_graph_iter(bad_graph))


graph_iter_testcases = {
    **outer_in_iter_testcases,
    "two_node_loop": (m.nx.DiGraph([(0, 1), (1, 0)]), [set([0, 1])],),
    "three_node_loop": (m.nx.DiGraph([(0, 1), (1, 2), (2, 0)]), [set([0, 1, 2])],),
    "path_to_three_node_loop": (
        m.nx.DiGraph([(4, 3), (3, 2), (0, 1), (1, 2), (2, 0),]),
        [set([0, 1, 2]), set([3]), set([4]),],
    ),
    "two_two_node_loops": (
        m.nx.DiGraph([(0, 1), (1, 0), (0, 2), (2, 0)]),
        [set([0, 1, 2])],
    ),
    "nested_three_and_two_node_loops": (
        m.nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 1), (1, 0), (0, 2), (2, 0)],),
        [set([0, 1, 2])],
    ),
}


@pytest.mark.parametrize(
    "graph, expected_nodes",
    graph_iter_testcases.values(),
    ids=graph_iter_testcases.keys(),
)
def test_outer_in_graph_iter(graph, expected_nodes):
    nodes = list(m.outer_in_graph_iter(graph))
    # visits all nodes
    assert set(graph.nodes()) == set().union(*nodes)

    # visits each node once
    for node_set in nodes:
        assert all(
            node_set.isdisjoint(other_node_set)
            for other_node_set in nodes
            if other_node_set != node_set
        )

    # only visits node when its deps were already visited or in the set to score
    visited = set()
    for node_set in nodes:
        for node in node_set:
            assert all(
                dst in (visited | node_set) for (_, dst) in graph.out_edges(node)
            )
        visited |= node_set

    # returns expected values
    assert nodes == expected_nodes
    assert len(nodes) == len(expected_nodes)
