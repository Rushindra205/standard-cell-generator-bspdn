from collections import defaultdict


class TopologyAnalyzer:

    def __init__(self, graph):
        self.graph = graph

    def parallel_groups(self):
        """
        Find devices connected between the same two diffusion nodes.

        Returns:
            [(endpoint_pair, [devices]), ...]
        """

        buckets = defaultdict(list)

        for transistor in self.graph.devices():
            u, v = self.graph.device_endpoints(transistor)
            buckets[frozenset((u, v))].append(transistor)

        groups = []

        for key, members in buckets.items():

            if len(members) > 1:

                if len(key) > 1:
                    nodes = tuple(sorted(key))
                else:
                    node = next(iter(key))
                    nodes = (node, node)

                groups.append((nodes, members))

        groups.sort(key=lambda group: -len(group[1]))

        return groups

    def series_pairs(self):
        """
        Find pairs of devices connected in series through an internal
        diffusion node.

        A valid series pair must:
            1. share exactly one diffusion node,
            2. share an internal node,
            3. have exactly two devices connected to that node.
        """

        pairs = []

        devices = self.graph.devices()

        for i in range(len(devices)):

            for j in range(i + 1, len(devices)):

                shared = self.graph.shared_nodes(
                    devices[i],
                    devices[j]
                )

                if len(shared) != 1:
                    continue

                node = next(iter(shared))

                if not self.graph.is_internal(node):
                    continue

                if self.graph.device_degree(node) == 2:
                    pairs.append(
                        (devices[i], devices[j], node)
                    )

        return pairs

    def diffusion_sharing_pairs(self):
        """
        Find topology-based candidates for physical diffusion sharing
        or transistor adjacency.

        Returns:
            (transistor_1, transistor_2, shared_node, relation)

        relation may be:
            - parallel
            - shared rail
            - shared pin
            - series
            - common node

        These are topology-level candidates only. They do not imply
        that the final physical layout must use diffusion sharing.
        """

        candidates = []

        devices = self.graph.devices()

        for i in range(len(devices)):

            for j in range(i + 1, len(devices)):

                shared = self.graph.shared_nodes(
                    devices[i],
                    devices[j]
                )

                if not shared:
                    continue

                if len(shared) == 2:
                    relation = "parallel"

                else:
                    node = next(iter(shared))

                    if self.graph.is_supply(node):
                        relation = "shared rail"

                    elif not self.graph.is_internal(node):
                        relation = "shared pin"

                    elif self.graph.device_degree(node) == 2:
                        relation = "series"

                    else:
                        relation = "common node"

                for node in sorted(shared):

                    candidates.append(
                        (
                            devices[i],
                            devices[j],
                            node,
                            relation,
                        )
                    )

        return candidates

    def series_units(self):
        """
        Find series relationships between parallel transistor groups.

        A parallel group is treated as one topology unit.

        Example:

            A1 || A2
                 |
                 X
                 |
            B1 || B2

        becomes:

            [A1, A2] -- X -- [B1, B2]

        Returns:
            (unit_a, unit_b, shared_node)
        """

        units = []
        claimed = set()

        # -----------------------------------------------------
        # Create units from parallel groups
        # -----------------------------------------------------

        for _, members in self.parallel_groups():

            units.append(list(members))

            for transistor in members:
                claimed.add(transistor.name)

        # -----------------------------------------------------
        # Add individual devices not belonging to a group
        # -----------------------------------------------------

        for transistor in self.graph.devices():

            if transistor.name not in claimed:
                units.append([transistor])

        # -----------------------------------------------------
        # Determine which diffusion nodes touch each unit
        # -----------------------------------------------------

        def endpoints(unit):
            return set(
                self.graph.device_endpoints(unit[0])
            )

        touching = defaultdict(list)

        for index, unit in enumerate(units):

            for node in endpoints(unit):
                touching[node].append(index)

        # -----------------------------------------------------
        # Find internal nodes connecting exactly two units
        # -----------------------------------------------------

        series = []

        for node, indices in touching.items():

            if not self.graph.is_internal(node):
                continue

            if len(indices) != 2:
                continue

            a, b = indices

            if a != b:
                series.append(
                    (
                        units[a],
                        units[b],
                        node,
                    )
                )

        return series

    def describe_unit(self, unit):
        """
        Return a readable representation of a topology unit.

        Example:
            [T1, T2] -> A1 || A2
            [T3]     -> A3
        """

        gates = [
            transistor.gate.name
            for transistor in unit
        ]

        if len(gates) > 1:
            return " || ".join(gates)

        return gates[0]

    def node_connectivity(self):
        """
        Return connectivity information for every diffusion node.

        Each result contains:
            - node
            - supply status
            - finger degree
            - device degree
            - source/drain connections
        """

        rows = []

        for node in sorted(self.graph.vertices):

            terminals = []

            for transistor in self.graph.devices_at(node):

                where = []

                if transistor.source.name == node:
                    where.append("S")

                if transistor.drain.name == node:
                    where.append("D")

                terminals.append(
                    (
                        transistor,
                        "/".join(where) or "?"
                    )
                )

            rows.append(
                {
                    "node": node,
                    "is_supply": self.graph.is_supply(node),
                    "finger_degree": self.graph.degree(node),
                    "device_degree": self.graph.device_degree(node),
                    "terminals": terminals,
                }
            )

        # Internal nodes first, supply nodes last.
        rows.sort(
            key=lambda row: (
                row["is_supply"],
                row["node"]
            )
        )

        return rows