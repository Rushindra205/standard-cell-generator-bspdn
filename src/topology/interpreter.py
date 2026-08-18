from topology.graph import TransistorGraph

class TopologyModel:
    """stores the topology repn of a cell."""

    def __init__(self, cell, pullup, pulldown):
        self.cell = cell
        self.pullup = pullup
        self.pulldown = pulldown

    def __repr__(self):
        return (
            f"<TopologyModel {self.cell.name} "
            f"PUN={len(self.pullup.edges)} edges "
            f"PDN={len(self.pulldown.edges)} edges>"
        )

class TopologyInterpreter:

    def __init__(self, cell):
        self.cell = cell

    def build(self, expand_multiplicity=True, split_supplies=False):
        """Build the two networks from a parsed Cell."""

        pullup, pulldown = build_graphs(
            self.cell,
            expand_multiplicity=expand_multiplicity,
            split_supplies=split_supplies
        )

        return TopologyModel(
            self.cell,
            pullup,
            pulldown,
        )



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

    pullup = TransistorGraph(
        name=cell.name,
        network="pull-up",
        supplies=supplies, 
        terminals=terminals,
        )
    
    pulldown = TransistorGraph(
        name=cell.name,
        network="pull-down",
        supplies=supplies,
        terminals=terminals,
    )

    counter = 0

    for transistor in cell.transistors.values():

        if transistor.type == "PMOS":
            graph = pullup
        elif transistor.type == "NMOS":
            graph = pulldown
        else:
            raise ValueError(f"Unknown transistor type: {transistor.type}")

        u = transistor.source.name
        v = transistor.drain.name
        
        if split_supplies:
            if u in supplies:
                u = f"{u}#{counter}"
                counter += 1
            if v in supplies:
                v = f"{v}#{counter}"
                counter += 1

        if expand_multiplicity:
            fingers = max(1, transistor.multiplicity)
        else:
            fingers = 1

        for i in range(fingers):
            if fingers == 1:
                edge_id = transistor.name
            else:
                edge_id = f"{transistor.name}#{i}"
            
            graph.add_edge(
                u=u, v=v,
                gate=transistor.gate.name,
                transistor=transistor,
                wgaa=transistor.wgaa,
                finger_index=i,
                finger_count=fingers,
                edge_id=edge_id,
            )

    return pullup, pulldown


def is_hierarchical_cell(cell):
    """
    True when a cell parsed with no transistors at all.

    GT3's dffasync_x1 is built from six nand3_x1 instances written as X
    lines rather than from M lines, so a transistor-level parser sees an
    empty cell. That is worth reporting rather than drawing an empty graph.
    """
    return len(cell.instances) > 0