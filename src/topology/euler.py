from topology.graph import TransistorGraph

class EulerAnalyzer:
    def __init__(self, graph: TransistorGraph):
        self.graph = graph

    def euler_status(self):
        """
        Whether this network can be laid out as one unbroken diffusion
        chain, and if not, why. Returns a dict so callers can act on it.
        """
        components = self.graph.connected_components()
        odd = self.graph.odd_degree_vertices()

        if not self.graph.edges:
            return {"kind": "empty", "ok": True, "odd": [],
                    "components": components,
                    "reason": "no transistors in this network"}

        if len(components) > 1:
            return {"kind": "none", "ok": False, "odd": odd,
                    "components": components,
                    "reason": f"graph is in {len(components)} disconnected "
                              f"pieces; no single walk can cover them all"}

        if len(odd) == 0:
            return {"kind": "cycle", "ok": True, "odd": [],
                    "components": components,
                    "reason": "every vertex has even degree"}

        if len(odd) == 2:
            return {"kind": "trail", "ok": True, "odd": odd,
                    "components": components,
                    "reason": f"exactly two odd-degree vertices "
                              f"({odd[0]}, {odd[1]}) -- the two ends of "
                              f"the chain"}

        return {"kind": "none", "ok": False, "odd": odd,
                "components": components,
                "reason": f"{len(odd)} odd-degree vertices; an Euler path "
                          f"allows at most 2"}

    def has_euler_path(self):
        return self.euler_status()["ok"]

    def dummy_edges_needed_lower_bound(self):
        """
        Lower bound on dummy edges required to make an Euler path exist,
        ignoring folding.

        Joining c components costs c-1 edges. Fixing 2k odd vertices costs
        k-1 more, since a trail may keep two of them odd. The two overlap --
        a dummy that bridges two components also flips two parities -- so
        take the larger.
        """
        status = self.euler_status()
        if status["ok"]:
            return 0
        connect = max(0, len(status["components"]) - 1)
        parity = max(0, len(status["odd"]) // 2 - 1)
        return max(connect, parity)

    # --------------------------------------------------- Euler traversal

    def _is_valid_walk(self, path, start):
        current = start
        for edge in path:
            if current not in (edge.u, edge.v):
                return False
            current = current if edge.u == edge.v else edge.other(current)
        return True

    def path_start_vertex(self, path):
        """
        Recover the vertex an edge-list path begins at.

        Inspecting only the first two edges is not enough. When they are
        parallel or antiparallel -- two pull-up devices both running vdd to
        Y, say -- both endpoints of edge 0 are shared with edge 1, and no
        local test can tell which end the walk started from. So test each
        endpoint against the whole walk.
        """
        if not path:
            return None
        for candidate in (path[0].u, path[0].v):
            if self._is_valid_walk(path, candidate):
                return candidate
        return path[0].u

    def find_euler_path(self, start=None):
        """
        One Euler path as a list of edges in traversal order, or None if
        the network admits none. Hierholzer's algorithm, iterative.

        A trail must start at one of the two odd-degree vertices; a cycle
        may start anywhere.
        """
        status = self.euler_status()
        if not status["ok"] or not self.graph.edges:
            return None if not status["ok"] else []

        if start is None:
            start = status["odd"][0] if status["kind"] == "trail" \
                else sorted(self.graph.vertices)[0]

        unused = {e.id for e in self.graph.edges}
        adjacency = {v: list(self.graph.adjacency[v]) for v in self.graph.vertices}

        stack = [(start, None)]
        circuit = []

        while stack:
            vertex, arriving = stack[-1]
            bucket = adjacency[vertex]

            while bucket and bucket[-1].id not in unused:
                bucket.pop()

            if bucket:
                edge = bucket.pop()
                unused.discard(edge.id)
                nxt = vertex if edge.u == edge.v else edge.other(vertex)
                stack.append((nxt, edge))
            else:
                stack.pop()
                if arriving is not None:
                    circuit.append(arriving)

        circuit.reverse()
        return circuit if len(circuit) == len(self.graph.edges) else None

    def enumerate_euler_paths(self, limit=20, max_nodes=100000):
        """
        Distinct Euler paths, up to `limit`.

        A network normally has many, and they are not interchangeable: each
        is a different left-to-right transistor order, and how well the
        pull-up order lines up against the pull-down order decides the final
        cell width. Choosing between them is a later stage; enumerating them
        is what makes that choice possible.

        Orderings that produce the same gate sequence are collapsed, since
        two fingers of one device are indistinguishable in the layout.
        Backtracking DFS, bounded by `max_nodes` so a large cell cannot
        hang the tool.
        """
        status = self.euler_status()
        if not status["ok"] or not self.graph.edges:
            return []

        starts = status["odd"] if status["kind"] == "trail" \
            else sorted(self.graph.vertices)

        found, seen = [], set()
        budget = [max_nodes]

        def dfs(vertex, used, trail):
            if budget[0] <= 0 or len(found) >= limit:
                return
            budget[0] -= 1

            if len(trail) == len(self.graph.edges):
                signature = tuple(e.gate for e in trail)
                if signature not in seen:
                    seen.add(signature)
                    found.append(list(trail))
                return

            tried = set()
            for edge in self.graph.adjacency[vertex]:
                if edge.id in used:
                    continue
                nxt = vertex if edge.u == edge.v else edge.other(vertex)
                key = (edge.gate, nxt)
                if key in tried:
                    continue
                tried.add(key)

                used.add(edge.id)
                trail.append(edge)
                dfs(nxt, used, trail)
                trail.pop()
                used.discard(edge.id)

                if len(found) >= limit or budget[0] <= 0:
                    return

        for start in starts:
            if len(found) >= limit or budget[0] <= 0:
                break
            dfs(start, set(), [])

        return found

    def path_vertex_sequence(self, path, start=None):
        """The diffusion nodes visited, in order: v0, v1, ... vn."""
        if not path:
            return []
        if start is None:
            start = self.path_start_vertex(path)
        seq, current = [start], start
        for edge in path:
            current = current if edge.u == edge.v else edge.other(current)
            seq.append(current)
        return seq
