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
        if not self.edges:
            return False
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

    

    # ------------------------------------------------------- Euler status

    

    # ----------------------------------------------------------- rendering

    def summary(self):
        return (f"{self.network}: {len(self.vertices)} vertices, "
                f"{len(self.edges)} edges, "
                f"{len(self.odd_degree_vertices())} odd-degree, "
                f"{len(self.connected_components())} component(s)")

    def describe(self, indent="  ", show_connections=True):
        lines = [self.summary()]
        components = self.connected_components()

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

        if len(components) > 1:
            lines.append(f"{indent}components:")
            for i, comp in enumerate(components):
                lines.append(f"{indent}  {i}: {sorted(comp)}")

        return "\n".join(lines)



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


