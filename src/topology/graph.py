from collections import defaultdict


class Edge:
    """
    One edge of the transistor graph.

    Normally one finger of a transistor. It can also be a dummy edge
    inserted later to repair degree parity, in which case `transistor` is
    None.
    """

    def __init__(self, edge_id, u, v, gate=None, transistor=None,
                 wgaa=None, is_dummy=False,
                 finger_index=0, finger_count=1):
        self.id = edge_id
        self.u = u                        # one diffusion endpoint
        self.v = v                        # the other
        self.gate = gate                  # gate net name (edge label)
        self.transistor = transistor      # source Transistor, None if dummy
        self.wgaa = wgaa                  # nanosheet width, microns
        self.is_dummy = is_dummy
        self.finger_index = finger_index  # which finger of the parent device
        self.finger_count = finger_count  # total fingers of the parent

    @property
    def is_finger(self):
        return self.finger_count > 1

    def other(self, vertex):
        """Given one endpoint, return the other."""
        if vertex == self.u:
            return self.v
        if vertex == self.v:
            return self.u
        raise ValueError(f"{vertex} is not an endpoint of edge {self.id}")

    def __repr__(self):
        if self.is_dummy:
            return f"<dummy {self.u}--{self.v}>"
        tag = f" f{self.finger_index + 1}/{self.finger_count}" \
            if self.is_finger else ""
        return f"<{self.id} {self.u}--[{self.gate}]--{self.v}{tag}>"


class TransistorGraph:
    """
    Multigraph over diffusion nodes.

    Parallel edges are the norm, not an edge case. The two PMOS of a NAND2
    both run vdd to Y, and the twelve fingers of an inv_x12 all run vdd to
    Y. Collapsing them would throw away real devices.
    """

    def __init__(self, name="", network="", supplies=None, terminals=None):
        self.name = name
        self.network = network            # "pull-up" or "pull-down"
        self.edges = []
        self.adjacency = defaultdict(list)
        self.supplies = set(supplies or ())    # vdd / vss
        self.terminals = set(terminals or ())  # every cell pin
        self._auto_id = 0

    # ---------------------------------------------------------------- build

    def add_edge(self, u, v, gate=None, transistor=None, wgaa=None,
                 is_dummy=False, finger_index=0, finger_count=1,
                 edge_id=None):
        if edge_id is None:
            edge_id = f"e{self._auto_id}"
            self._auto_id += 1

        edge = Edge(edge_id, u, v, gate, transistor, wgaa,
                    is_dummy, finger_index, finger_count)
        self.edges.append(edge)
        self.adjacency[u].append(edge)
        # A self-loop is stored once but counts 2 toward degree.
        if u != v:
            self.adjacency[v].append(edge)
        return edge

    def add_dummy_edge(self, u, v):
        eid = f"dummy{self._auto_id}"
        self._auto_id += 1
        return self.add_edge(u, v, is_dummy=True, edge_id=eid)

    # ------------------------------------------------------------- queries

    @property
    def vertices(self):
        return list(self.adjacency.keys())

    def degree(self, vertex):
        """
        Edge-ends at this vertex. A self-loop contributes 2. This parity is
        what the Euler condition is stated in terms of.
        """
        return sum(2 if e.u == e.v else 1 for e in self.adjacency[vertex])

    def degrees(self):
        return {v: self.degree(v) for v in self.vertices}

    def odd_degree_vertices(self):
        return sorted(v for v in self.vertices if self.degree(v) % 2 == 1)

    def neighbours(self, vertex):
        """Distinct vertices reachable in one edge, with edge multiplicity."""
        counts = defaultdict(int)
        for edge in self.adjacency[vertex]:
            other = vertex if edge.u == edge.v else edge.other(vertex)
            counts[other] += 1
        return dict(counts)

    def connected_components(self):
        """Vertex sets that carry at least one edge, largest first."""
        seen, components = set(), []

        for start in self.vertices:
            if start in seen or not self.adjacency[start]:
                continue
            stack, comp = [start], set()
            while stack:
                v = stack.pop()
                if v in seen:
                    continue
                seen.add(v)
                comp.add(v)
                for edge in self.adjacency[v]:
                    nxt = v if edge.u == edge.v else edge.other(v)
                    if nxt not in seen:
                        stack.append(nxt)
            components.append(comp)

        components.sort(key=len, reverse=True)
        return components

    def is_connected(self):
        return len(self.connected_components()) <= 1

    def is_supply(self, node):
        """
        True for a power rail. Kept as a set on the graph rather than
        guessed from the name, since a BSPDN cell may rename its rails.
        """
        return node in self.supplies or node.split("#")[0] in self.supplies

    def is_internal(self, node):
        """
        True for a node that is not a cell pin.

        Only an internal node can be a series junction. A pin is where the
        network meets the outside world -- the output Y, or a rail -- so two
        devices meeting there are the ends of separate branches, not a
        conduction path passing through both.
        """
        base = node.split("#")[0]
        return base not in self.terminals and base not in self.supplies

    def copy(self):
        g = TransistorGraph(self.name, self.network,
                            self.supplies, self.terminals)
        for e in self.edges:
            g.add_edge(e.u, e.v, e.gate, e.transistor, e.wgaa,
                       e.is_dummy, e.finger_index, e.finger_count,
                       edge_id=e.id)
        g._auto_id = self._auto_id
        return g

    # ------------------------------------------------- device-level view
    #
    # Degree and the Euler condition are counted over FINGERS, because each
    # finger is its own poly column. Series/parallel structure, though, is a
    # property of the DEVICES: the twelve fingers of an inv_x12 are one
    # transistor, not twelve transistors in parallel with each other. These
    # helpers collapse fingers back to devices.

    def devices(self):
        """Unique transistors in this network, in netlist order."""
        seen, out = set(), []
        for edge in self.edges:
            t = edge.transistor
            if t is None or t.name in seen:
                continue
            seen.add(t.name)
            out.append(t)
        return out

    def device_endpoints(self, transistor):
        """The (source, drain) diffusion nodes of a device, as placed."""
        for edge in self.edges:
            if edge.transistor is transistor:
                return (edge.u, edge.v)
        return None

    def device_fingers(self, transistor):
        return sum(1 for e in self.edges if e.transistor is transistor)

    def devices_at(self, vertex):
        """Devices with a source or drain on this diffusion node."""
        seen, out = set(), []
        for edge in self.adjacency[vertex]:
            t = edge.transistor
            if t is None or t.name in seen:
                continue
            seen.add(t.name)
            out.append(t)
        return out

    def device_degree(self, vertex):
        """Distinct devices touching this node, ignoring finger count."""
        return len(self.devices_at(vertex))

    def shared_nodes(self, t1, t2):
        """Diffusion nodes common to two devices."""
        a, b = self.device_endpoints(t1), self.device_endpoints(t2)
        if a is None or b is None:
            return set()
        return set(a) & set(b)

    def parallel_groups(self):
        """
        Devices wired in parallel: same two diffusion nodes at both ends,
        so they conduct between the same pair. Returns a list of
        (endpoint_pair, [devices]) for groups of two or more.
        """
        buckets = defaultdict(list)
        for t in self.devices():
            u, v = self.device_endpoints(t)
            buckets[frozenset((u, v))].append(t)

        groups = []
        for key, members in buckets.items():
            if len(members) > 1:
                nodes = tuple(sorted(key)) if len(key) > 1 \
                    else (next(iter(key)),) * 2
                groups.append((nodes, members))
        groups.sort(key=lambda g: -len(g[1]))
        return groups

    def series_pairs(self):
        """
        Devices wired in series: they share exactly one diffusion node, that
        node is internal, and no other device touches it. Current must pass
        through both.

        The shared node must be internal -- not a rail, not the output.
        Two pull-down devices both tied to vss are the grounded ends of two
        separate branches, and two devices both tied to Y are their top
        ends; in each case they are in parallel, and no current passes
        through both. Without this check an aoi22 pull-down reports its
        A-branch and B-branch as series, which is backwards.

        Returns a list of (t1, t2, shared_node).
        """
        pairs = []
        devs = self.devices()
        for i in range(len(devs)):
            for j in range(i + 1, len(devs)):
                shared = self.shared_nodes(devs[i], devs[j])
                if len(shared) != 1:
                    continue
                node = next(iter(shared))
                if not self.is_internal(node):
                    continue
                if self.device_degree(node) == 2:
                    pairs.append((devs[i], devs[j], node))
        return pairs

    def diffusion_sharing_pairs(self):
        """
        Every pair of devices that could be abutted -- placed side by side
        sharing one diffusion region, with no break between them.

        A pair qualifies whenever they have a diffusion node in common,
        whether that node is internal or a supply rail. Two pull-up devices
        both on vdd can abut across the rail just as a series pair can abut
        across their internal node.

        Returns a list of (t1, t2, shared_node, relation).
        """
        out = []
        devs = self.devices()
        for i in range(len(devs)):
            for j in range(i + 1, len(devs)):
                shared = self.shared_nodes(devs[i], devs[j])
                if not shared:
                    continue
                if len(shared) == 2:
                    relation = "parallel"
                else:
                    node = next(iter(shared))
                    if self.is_supply(node):
                        relation = "shared rail"
                    elif not self.is_internal(node):
                        relation = "shared pin"
                    elif self.device_degree(node) == 2:
                        relation = "series"
                    else:
                        relation = "common node"
                for node in sorted(shared):
                    out.append((devs[i], devs[j], node, relation))
        return out

    def series_units(self):
        """
        Series structure at the level of parallel GROUPS, not just single
        devices.

        In an aoi22 pull-up, A1 and A2 sit in parallel, B1 and B2 sit in
        parallel, and the two groups are stacked in series. No individual
        pair qualifies as series -- the node between them carries four
        devices -- so a device-level test reports nothing and misses the
        structure entirely.

        So collapse each parallel group to one unit, then look for nodes
        that exactly two units touch. Returns a list of
        (unit_a, unit_b, shared_node), where a unit is a list of devices.
        """
        units = []
        claimed = set()

        for (_, members) in self.parallel_groups():
            units.append(list(members))
            claimed.update(t.name for t in members)

        for t in self.devices():
            if t.name not in claimed:
                units.append([t])

        def endpoints(unit):
            return set(self.device_endpoints(unit[0]))

        touching = defaultdict(list)
        for index, unit in enumerate(units):
            for node in endpoints(unit):
                touching[node].append(index)

        out = []
        for node, indices in touching.items():
            if not self.is_internal(node):
                continue
            if len(indices) == 2:
                a, b = indices
                # A parallel group already shares both its endpoints, so
                # skip a "series" reading of a group against itself.
                if a != b:
                    out.append((units[a], units[b], node))

        return out

    def describe_unit(self, unit):
        """'A1 || A2' for a parallel group, or just 'A1' for one device."""
        gates = [t.gate.name for t in unit]
        return " || ".join(gates) if len(gates) > 1 else gates[0]

    def node_connectivity(self):
        """
        For each diffusion node: which devices touch it, through which
        terminal, and the finger and device degrees.

        Returns an ordered list of dicts, supplies last so the internal
        nodes -- the ones that actually constrain placement -- read first.
        """
        rows = []

        for v in sorted(self.vertices):
            terminals = []
            for t in self.devices_at(v):
                where = []
                if t.source.name == v:
                    where.append("S")
                if t.drain.name == v:
                    where.append("D")
                terminals.append((t, "/".join(where) or "?"))

            rows.append({
                "node": v,
                "is_supply": self.is_supply(v),
                "finger_degree": self.degree(v),
                "device_degree": self.device_degree(v),
                "terminals": terminals,
            })

        rows.sort(key=lambda r: (r["is_supply"], r["node"]))
        return rows


    # ------------------------------------------------------- Euler status

    def euler_status(self):
        """
        Whether this network can be laid out as one unbroken diffusion
        chain, and if not, why. Returns a dict so callers can act on it.
        """
        components = self.connected_components()
        odd = self.odd_degree_vertices()

        if not self.edges:
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

    def dummy_edges_needed(self):
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
        if not status["ok"] or not self.edges:
            return None if not status["ok"] else []

        if start is None:
            start = status["odd"][0] if status["kind"] == "trail" \
                else sorted(self.vertices)[0]

        unused = {e.id for e in self.edges}
        adjacency = {v: list(self.adjacency[v]) for v in self.vertices}

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
        return circuit if len(circuit) == len(self.edges) else None

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
        if not status["ok"] or not self.edges:
            return []

        starts = status["odd"] if status["kind"] == "trail" \
            else sorted(self.vertices)

        found, seen = [], set()
        budget = [max_nodes]

        def dfs(vertex, used, trail):
            if budget[0] <= 0 or len(found) >= limit:
                return
            budget[0] -= 1

            if len(trail) == len(self.edges):
                signature = tuple(e.gate for e in trail)
                if signature not in seen:
                    seen.add(signature)
                    found.append(list(trail))
                return

            tried = set()
            for edge in self.adjacency[vertex]:
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


    # ----------------------------------------------------------- rendering

    def summary(self):
        return (f"{self.network}: {len(self.vertices)} vertices, "
                f"{len(self.edges)} edges, "
                f"{len(self.odd_degree_vertices())} odd-degree, "
                f"{len(self.connected_components())} component(s)")

    def describe(self, indent="  ", show_connections=True):
        status = self.euler_status()
        lines = [self.summary()]

        lines.append(f"{indent}vertices (diffusion nodes):")
        for v in sorted(self.vertices):
            d = self.degree(v)
            mark = "  <- odd" if d % 2 else ""
            lines.append(f"{indent}  {v:<12} degree {d}{mark}")

        lines.append(f"{indent}edges (transistors):")
        for e in self.edges:
            if e.is_dummy:
                lines.append(f"{indent}  {e.u} -- {e.v}   (dummy)")
                continue
            tag = f"   finger {e.finger_index + 1}/{e.finger_count}" \
                if e.is_finger else ""
            lines.append(f"{indent}  {e.u} --[{e.gate}]-- {e.v}"
                         f"   {e.id}{tag}")

        if show_connections:
            lines.append(f"{indent}connections:")
            for v in sorted(self.vertices):
                parts = []
                for other, count in sorted(self.neighbours(v).items()):
                    parts.append(f"{other} x{count}" if count > 1 else other)
                lines.append(f"{indent}  {v:<12} -> {', '.join(parts)}")

        components = status["components"]
        if len(components) > 1:
            lines.append(f"{indent}components:")
            for i, comp in enumerate(components):
                lines.append(f"{indent}  {i}: {sorted(comp)}")

        lines.append(f"{indent}euler: {status['kind']} -- {status['reason']}")
        return "\n".join(lines)

    def report(self, indent="  ", max_orderings=8):
        """
        Full connectivity report for this network, one section per question.
        """
        L = []
        w = indent
        status = self.euler_status()

        def head(text):
            L.append("")
            L.append(f"{text}")
            L.append("-" * len(text))

        # ---------------------------------------------- the graph itself
        L.append(f"{self.network.upper()}  ({self.summary()})")

        head(f"{w}connectivity graph")
        for e in self.edges:
            tag = f"   finger {e.finger_index + 1}/{e.finger_count}" \
                if e.is_finger else ""
            L.append(f"{w}  {e.u} --[{e.gate}]-- {e.v}   {e.id}{tag}")

        # ---------------------------------------------- series / parallel
        head(f"{w}series connections")
        series = self.series_pairs()
        if series:
            L.append(f"{w}  device pairs (current must pass through both):")
            for t1, t2, node in series:
                L.append(f"{w}    {t1.name} - {t2.name}"
                         f"   through {node}"
                         f"   (gates {t1.gate.name}, {t2.gate.name})")

        units = self.series_units()
        stacked = [(a, b, n) for a, b, n in units
                   if len(a) > 1 or len(b) > 1]
        if stacked:
            L.append(f"{w}  stacked groups:")
            for a, b, node in stacked:
                L.append(f"{w}    ({self.describe_unit(a)})"
                         f" - ({self.describe_unit(b)})"
                         f"   through {node}")

        if not series and not stacked:
            L.append(f"{w}  none")

        head(f"{w}parallel connections")
        groups = self.parallel_groups()
        if groups:
            for (a, b), members in groups:
                names = ", ".join(t.name for t in members)
                gates = ", ".join(sorted({t.gate.name for t in members}))
                L.append(f"{w}  {names}"
                         f"   both ends {a} / {b}"
                         f"   (gates {gates})")
        else:
            L.append(f"{w}  none")

        fingered = [t for t in self.devices() if self.device_fingers(t) > 1]
        if fingered:
            L.append(f"{w}  fingers of one device (parallel by "
                     f"construction, M in the netlist):")
            for t in fingered:
                L.append(f"{w}    {t.name}  M={self.device_fingers(t)}")

        # ---------------------------------------------- diffusion sharing
        head(f"{w}diffusion sharing opportunities")
        sharing = self.diffusion_sharing_pairs()
        if sharing:
            L.append(f"{w}  pairs that can abut with no diffusion break:")
            for t1, t2, node, relation in sharing:
                L.append(f"{w}    {t1.name} | {t2.name}"
                         f"   share {node}   [{relation}]")
        else:
            L.append(f"{w}  none -- every device is isolated")

        # ---------------------------------------------- per-node detail
        head(f"{w}diffusion nodes: degree and connected transistors")
        L.append(f"{w}  {'node':<10}{'fingers':>8}{'devices':>9}   "
                 f"transistors (terminal)")
        for row in self.node_connectivity():
            tag = "  [supply]" if row["is_supply"] else ""
            devs = ", ".join(f"{t.name}({term})"
                             for t, term in row["terminals"])
            L.append(f"{w}  {row['node']:<10}"
                     f"{row['finger_degree']:>8}"
                     f"{row['device_degree']:>9}   {devs}{tag}")

        # ---------------------------------------------- source/drain
        head(f"{w}source/drain relationships")
        for t in self.devices():
            u, v = self.device_endpoints(t)
            m = self.device_fingers(t)
            mtag = f"  M={m}" if m > 1 else ""
            L.append(f"{w}  {t.name:<8} S={t.source.name:<8} "
                     f"D={t.drain.name:<8} G={t.gate.name}{mtag}")

        # ---------------------------------------------- euler
        head(f"{w}euler path")
        L.append(f"{w}  {status['kind']} -- {status['reason']}")
        if status["odd"]:
            L.append(f"{w}  odd-degree nodes: {', '.join(status['odd'])}")
        if not status["ok"]:
            L.append(f"{w}  needs at least {self.dummy_edges_needed()} "
                     f"dummy edge(s), or folding, before a single "
                     f"unbroken chain is possible")

        head(f"{w}possible euler transistor orderings")
        if not status["ok"]:
            L.append(f"{w}  none -- no Euler path exists for this network")
        else:
            paths = self.enumerate_euler_paths(limit=max_orderings)
            if not paths:
                L.append(f"{w}  none found")
            else:
                L.append(f"{w}  {len(paths)} distinct gate ordering(s) "
                         f"shown (left to right = poly column order):")
                for i, path in enumerate(paths, 1):
                    gates = " | ".join(e.gate for e in path)
                    nodes = " - ".join(self.path_vertex_sequence(path))
                    L.append(f"{w}    {i}. {gates}")
                    L.append(f"{w}       nodes: {nodes}")

        return "\n".join(L)

    def to_dot(self):
        """
        Graphviz DOT. Render with:  dot -Tpng cell.dot -o cell.png
        Odd-degree vertices are shaded red -- those force dummy poly.
        """
        safe = f"{self.name}_{self.network}".replace(".", "_") \
            .replace("-", "_").replace(" ", "_")
        lines = [f'graph "{safe}" {{',
                 '  layout=neato;',
                 '  node [shape=circle, fontsize=10];',
                 '  edge [fontsize=9];']

        for v in sorted(self.vertices):
            odd = self.degree(v) % 2 == 1
            fill = "#ffd9d9" if odd else "#d9e9ff"
            lines.append(f'  "{v}" [label="{v}\\ndeg {self.degree(v)}", '
                         f'style=filled, fillcolor="{fill}"];')

        for e in self.edges:
            if e.is_dummy:
                lines.append(f'  "{e.u}" -- "{e.v}" '
                             f'[label="dummy", style=dashed, color=gray];')
            else:
                lines.append(f'  "{e.u}" -- "{e.v}" [label="{e.gate}"];')

        lines.append("}")
        return "\n".join(lines)

    def __repr__(self):
        return f"<TransistorGraph {self.name} {self.summary()}>"


# --------------------------------------------------------------------------
# Building the two networks from a parsed Cell
# --------------------------------------------------------------------------

def build_graphs(cell, expand_multiplicity=True, split_supplies=False):
    """
    Build the pull-up (PMOS) and pull-down (NMOS) graphs of one cell.

    Returns (pullup_graph, pulldown_graph).

    expand_multiplicity:
        True (default) -- a device with M=k becomes k parallel edges, one
            per finger. This is what is actually built: an inv_x12 pull-up
            is twelve poly columns, not one.
        False -- one edge per device regardless of M. Shows the logical
            topology, but understates width and can report the wrong Euler
            kind, since k fingers shift each endpoint's degree by k.

    split_supplies:
        True -- give each device its own copy of vdd/vss, so a chain cannot
            run through the power rail. Off by default: every pull-up
            device touching vdd meets at one vertex, which is what lets a
            long shared-diffusion chain exist at all.
    """
    supplies = set(cell.power_nets) | set(cell.ground_nets)

    terminals = (set(cell.input_nets) | set(cell.output_nets)
                 | set(cell.power_nets) | set(cell.ground_nets))

    pullup = TransistorGraph(cell.name, "pull-up", supplies, terminals)
    pulldown = TransistorGraph(cell.name, "pull-down", supplies, terminals)

    counter = 0

    for transistor in cell.transistors.values():
        graph = pullup if transistor.type == "PMOS" else pulldown

        u = transistor.source.name
        v = transistor.drain.name

        if split_supplies:
            if u in supplies:
                u = f"{u}#{counter}"
                counter += 1
            if v in supplies:
                v = f"{v}#{counter}"
                counter += 1

        fingers = max(1, transistor.multiplicity) if expand_multiplicity else 1

        for i in range(fingers):
            edge_id = transistor.name if fingers == 1 \
                else f"{transistor.name}#{i}"
            graph.add_edge(
                u, v,
                gate=transistor.gate.name,
                transistor=transistor,
                wgaa=transistor.wgaa,
                finger_index=i,
                finger_count=fingers,
                edge_id=edge_id,
            )

    return pullup, pulldown


def is_hierarchical(cell):
    """
    True when a cell parsed with no transistors at all.

    GT3's dffasync_x1 is built from six nand3_x1 instances written as X
    lines rather than from M lines, so a transistor-level parser sees an
    empty cell. That is worth reporting rather than drawing an empty graph.
    """
    return len(cell.transistors) == 0
