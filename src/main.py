import sys

from parser.cdl_parser import CDLParser

from topology.interpreter import TopologyInterpreter
from topology.analysis import TopologyAnalyzer
from topology.euler import EulerAnalyzer


def main():

    if len(sys.argv) != 2:
        print("Usage:")
        print("python src/main.py <cell_name>")
        print()
        print("Example:")
        print("python src/main.py and2_x1")
        return

    cell_name = sys.argv[1]

    # ---------------------------------------------------------
    # 1. Parse CDL -> Cell IR
    # ---------------------------------------------------------

    parser = CDLParser("Benchmarks/gt3_rvt.cdl")

    try:
        cell = parser.parse_cell(cell_name)
    except ValueError as e:
        print(e)
        return

    print("=" * 60)
    print("CELL")
    print("=" * 60)
    print(cell)

    # ---------------------------------------------------------
    # 2. Cell IR -> PUN / PDN Graphs
    # ---------------------------------------------------------

    interpreter = TopologyInterpreter(cell)

    topology = interpreter.build(
        expand_multiplicity=True,
        split_supplies=False
    )

    print("=" * 60)
    print("TOPOLOGY MODEL")
    print("=" * 60)
    print(topology)

    # ---------------------------------------------------------
    # 3. Analyze PUN
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("PULL-UP NETWORK (PMOS)")
    print("=" * 60)

    pun = topology.pullup

    print(pun.describe())

    pun_analyzer = TopologyAnalyzer(pun)
    pun_euler = EulerAnalyzer(pun)

    # Parallel structures
    print("\nParallel groups:")

    parallel_groups = pun_analyzer.parallel_groups()

    if parallel_groups:
        for nodes, devices in parallel_groups:
            names = [t.name for t in devices]
            gates = [t.gate.name for t in devices]

            print(
                f"  {nodes}: "
                f"{names} "
                f"(gates: {gates})"
            )
    else:
        print("  None")

    # Series structures
    print("\nSeries pairs:")

    series_pairs = pun_analyzer.series_pairs()

    if series_pairs:
        for t1, t2, node in series_pairs:
            print(
                f"  {t1.name} -- {node} -- {t2.name}"
            )
    else:
        print("  None")

    # Euler
    print("\nEuler analysis:")

    pun_status = pun_euler.euler_status()

    print(f"  Kind       : {pun_status['kind']}")
    print(f"  Euler path : {pun_status['ok']}")
    print(f"  Odd nodes  : {pun_status['odd']}")
    print(f"  Components : {len(pun_status['components'])}")
    print(f"  Reason     : {pun_status['reason']}")

    # ---------------------------------------------------------
    # 4. Analyze PDN
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("PULL-DOWN NETWORK (NMOS)")
    print("=" * 60)

    pdn = topology.pulldown

    print(pdn.describe())

    pdn_analyzer = TopologyAnalyzer(pdn)
    pdn_euler = EulerAnalyzer(pdn)

    # Parallel structures
    print("\nParallel groups:")

    parallel_groups = pdn_analyzer.parallel_groups()

    if parallel_groups:
        for nodes, devices in parallel_groups:

            print(" Parallel group:")
            print(f"  endpoints: {nodes}")

            gates = []

            for transistor in devices:
                gates.append(transistor.gate.name)

                print(
                    f" {transistor.name}: "
                    f"gate={transistor.gate.name}, "
                    f"M={transistor.multiplicity}, "
                )

            total_physical_edges = sum(
                max(1, transistor.multiplicity) 
                for transistor in devices
                    
            )

            print(f"gates: {' || '.join(gates)}")
            print(f"total physical edges: {total_physical_edges}")

    else:
        print("  None")

         
    # Series structures
    print("\nSeries pairs:")

    series_pairs = pdn_analyzer.series_pairs()

    if series_pairs:
        for t1, t2, node in series_pairs:
            print(
                f"  {t1.name} -- {node} -- {t2.name}"
            )
    else:
        print("  None")

    # Series units
    print("\nSeries units:")

    series_units = pdn_analyzer.series_units()

    if series_units:
        for unit_a, unit_b, node in series_units:

            print(
                f"  {pdn_analyzer.describe_unit(unit_a)}"
                f" -- {node} -- "
                f"{pdn_analyzer.describe_unit(unit_b)}"
            )
    else:
        print("  None")

    # Euler
    print("\nEuler analysis:")

    pdn_status = pdn_euler.euler_status()

    print(f"  Kind       : {pdn_status['kind']}")
    print(f"  Euler path : {pdn_status['ok']}")
    print(f"  Odd nodes  : {pdn_status['odd']}")
    print(f"  Components : {len(pdn_status['components'])}")
    print(f"  Reason     : {pdn_status['reason']}")

    # ---------------------------------------------------------
    # 5. Euler candidate paths
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("EULER CANDIDATE PATHS")
    print("=" * 60)

    for name, graph, analyzer in [
        ("PUN", pun, pun_euler),
        ("PDN", pdn, pdn_euler),
    ]:

        print(f"\n{name}:")

        paths = analyzer.enumerate_euler_paths(
            limit=10
        )

        if not paths:
            print("  No Euler paths available.")
            continue

        for i, path in enumerate(paths, 1):
            analyzer = EulerAnalyzer(graph)

            start = analyzer.path_start_vertex(path)
            diffusion = analyzer.path_vertex_sequence(path, start)

            gates = [edge.gate for edge in path]

            print(
                f"  Path {i}: \n"
                f" start: {start}\n"
                f" Gates: {' -> '.join(gates)}\n"
                f" Diffusion: {' -> '.join(diffusion)}\n"
                f" End: {diffusion[-1]}"
            )

    # ---------------------------------------------------------
    # 6. Diffusion-sharing candidates
    # ---------------------------------------------------------

    print("\n" + "=" * 60)
    print("DIFFUSION-SHARING CANDIDATES")
    print("=" * 60)

    for name, analyzer in [
        ("PUN", pun_analyzer),
        ("PDN", pdn_analyzer),
    ]:

        print(f"\n{name}:")

        sharing = analyzer.diffusion_sharing_pairs()

        if not sharing:
            print("  None")
            continue

        for t1, t2, node, relation in sharing:

            print(
                f"  {t1.name} <-> {t2.name} \n"
                f" shared node: {node} \n"
                f" relation: {relation}\n"
                f" {t1.name} gate: {t1.gate.name}, "
                f"M={t1.multiplicity} \n"

                f" {t2.name} gate: {t2.gate.name}, "
                f"M={t2.multiplicity}"
            )


if __name__ == "__main__":
    main()