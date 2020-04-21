import pytest

import depobs.worker.tasks as tasks


outer_in_iter_failing_testcases = {
    "null_graph": tasks.nx.empty_graph(n=0, create_using=tasks.nx.DiGraph),
    "self_loop": tasks.nx.DiGraph([(0, 0)]),
    "two_node_loop": tasks.nx.DiGraph([(0, 1), (1, 0)]),
    "three_node_loop": tasks.nx.DiGraph([(0, 1), (1, 2), (2, 0)]),
    "two_two_node_loops": tasks.nx.DiGraph([(0, 1), (1, 0), (0, 2), (2, 0)]),
    "nested_three_and_two_node_loops": tasks.nx.DiGraph(
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
        next(tasks.outer_in_iter(bad_graph))


outer_in_iter_testcases = {
    "five_node_path_graph": (
        tasks.nx.path_graph(5, create_using=tasks.nx.DiGraph),
        [set([i]) for i in range(4, -1, -1)],
    ),
    "small_tree": (
        tasks.nx.DiGraph([(0, 1), (1, 2), (1, 3), (1, 4), (2, 4)]),
        [set([3, 4]), set([2]), set([1]), set([0])],
    ),
}


@pytest.mark.parametrize(
    "graph, expected_nodes",
    outer_in_iter_testcases.values(),
    ids=outer_in_iter_testcases.keys(),
)
def test_outer_in_iter(graph, expected_nodes):
    nodes = list(tasks.outer_in_iter(graph))
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
