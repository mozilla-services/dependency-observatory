import pytest

import depobs.worker.tasks as tasks


@pytest.mark.parametrize(
    "bad_graph, expected_exception",
    [
        (tasks.nx.empty_graph(n=0, create_using=tasks.nx.DiGraph), Exception)
        # tasks.nx.wheel_graph(3, create_using=tasks.nx.DiGraph),
    ],
    ids=[
        "null_graph",
        # "wheel_graph(3)"
    ],
)
def test_outer_in_iter_bad_input(bad_graph, expected_exception):
    with pytest.raises(expected_exception):
        next(tasks.outer_in_iter(bad_graph))


@pytest.mark.parametrize(
    "graph, expected_nodes",
    [
        (
            tasks.nx.path_graph(5, create_using=tasks.nx.DiGraph),
            [set([i]) for i in range(4, -1, -1)],
        ),
        (
            tasks.nx.DiGraph([(0, 1), (1, 2), (1, 3), (1, 4), (2, 4)]),
            [set([3, 4]), set([2]), set([1]), set([0])],
        ),
    ],
)
def test_outer_in_iter_iters(graph, expected_nodes):
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
