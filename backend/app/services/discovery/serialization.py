"""Flatten PM4Py structures and prepare a deterministic, dependency-free Flow layout."""

from collections import defaultdict, deque

from app.services.discovery.log import stable_id


def serialize_tree(tree, process: str, path: str = "0") -> dict:
    return {
        "id": stable_id("tree", process, path),
        "operator": tree.operator.value if tree.operator else None,
        "label": tree.label,
        "silent": tree.operator is None and tree.label is None,
        "children": [
            serialize_tree(child, process, f"{path}.{index}")
            for index, child in enumerate(tree.children)
        ],
    }


def serialize_petri(net, initial, final, process: str) -> dict:
    # PM4Py internal names can contain generated UUIDs. Export opaque IDs scoped to this model.
    places = sorted(net.places, key=lambda place: str(place.name))
    transitions = sorted(net.transitions, key=lambda item: (item.label or "", str(item.name)))
    ids = {place: f"place_{index}" for index, place in enumerate(places)}
    ids.update(
        {transition: f"petri_transition_{index}" for index, transition in enumerate(transitions)}
    )
    arcs = sorted(net.arcs, key=lambda arc: (ids[arc.source], ids[arc.target]))
    return {
        "places": [
            {
                "id": ids[place],
                "initial_tokens": int(initial.get(place, 0)),
                "final_tokens": int(final.get(place, 0)),
            }
            for place in places
        ],
        "transitions": [
            {
                "id": ids[item],
                "label": item.label,
                "silent": item.label is None,
                "activity_id": stable_id("activity", process, item.label)
                if item.label is not None
                else None,
            }
            for item in transitions
        ],
        "arcs": [
            {
                "id": f"arc_{index}",
                "source": ids[arc.source],
                "target": ids[arc.target],
                "weight": int(arc.weight),
            }
            for index, arc in enumerate(arcs)
        ],
    }


def graph_components(nodes: list[str], pairs: list[tuple[str, str]]) -> list[list[str]]:
    """Iterative Kosaraju avoids recursion limits on long DFGs. Graph cycles are not causality."""
    forward, reverse = defaultdict(list), defaultdict(list)
    for source, target in pairs:
        forward[source].append(target)
        reverse[target].append(source)
    visited, order = set(), []
    for root in nodes:
        if root in visited:
            continue
        stack = [(root, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                order.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((target, False) for target in forward[node] if target not in visited)
    assigned, groups = set(), []
    for root in reversed(order):
        if root in assigned:
            continue
        group, stack = [], [root]
        assigned.add(root)
        while stack:
            node = stack.pop()
            group.append(node)
            for target in reverse[node]:
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        groups.append(sorted(group))
    return sorted(groups)


def flow_model(activities: list[dict], transitions: list[dict]) -> dict:
    neighbors = defaultdict(list)
    for edge in transitions:
        neighbors[edge["source"]].append(edge["target"])
    starts = [item["id"] for item in activities if item["start_frequency"]]
    levels = dict.fromkeys(starts, 0)
    queue = deque(starts)

    def traverse():
        while queue:
            source = queue.popleft()
            for target in sorted(neighbors[source]):
                if target not in levels:
                    levels[target] = levels[source] + 1
                    queue.append(target)

    traverse()
    for item in activities:
        if item["id"] not in levels:
            levels[item["id"]] = max(levels.values(), default=-1) + 1
            queue.append(item["id"])
            traverse()
    rows, nodes = defaultdict(int), []
    for item in activities:
        level = levels[item["id"]]
        nodes.append(
            {
                "id": item["id"],
                "type": "default",
                "data": item,
                "position": {"x": level * 280.0, "y": rows[level] * 140.0},
            }
        )
        rows[level] += 1
    return {
        "nodes": nodes,
        "edges": [
            {
                "id": edge["id"],
                "source": edge["source"],
                "target": edge["target"],
                "type": "smoothstep",
                "label": str(edge["frequency"]),
                "data": edge,
            }
            for edge in transitions
        ],
    }
