from parser.cell import Cell
from parser.net import Net
from parser.transistor import Transistor

class CDLParser:
    """
    Parses a CDL standard cell library.
    """

    def __init__(self, filepath):
        self.filepath = filepath

    def parse_cell(self, cell_name):
        """
        Returns every line belonging to one .SUBCKT.
        """

        with open(self.filepath, "r") as file:

            for line in file:

                line = line.strip()

                if line.startswith(".SUBCKT"):

                    tokens = line.split()

                    if len(tokens) >= 2 and tokens[1] == cell_name:

                        cell = Cell(tokens[1])

                        for line in file:

                            line = line.strip()

                            if line.startswith("*.PININFO"):
                                self._parse_pininfo(line, cell)

                            elif line.startswith("M"):
                                self._parse_transistor(line, cell)

                            elif line.startswith(".ENDS"):
                                break

                        return cell


        raise ValueError(f"Cell '{cell_name}' not found in {self.filepath}.")

    def _parse_pininfo(self, line, cell):

        tokens = line.replace("*.PININFO", "").strip().split()

        for token in tokens:

            name, pin_type = token.split(":")

            if pin_type == "I":
                net_type = "INPUT"
            elif pin_type == "O":
                net_type = "OUTPUT"
            elif pin_type == "P":
                net_type = "POWER"
            elif pin_type == "G":
                net_type = "GROUND"
            else:
                continue  # Skip unknown pin types

            net = Net(name, net_type)
            cell.add_net(net)

        
                  
    def _get_or_create_net(self, cell, net_name):
        if net_name in cell.nets:
            return cell.nets[net_name]
        net = Net(net_name, "INTERNAL")  # Default type for internal nets
        cell.add_net(net)
        return net

    def _parse_transistor(self, line, cell):

        tokens = line.split()

        name = tokens[0]
        drain_name = tokens[1]
        gate_name = tokens[2]   
        source_name = tokens[3]
        bulk_name = tokens[4]

        model = tokens[5]

        if model.upper().startswith("NMOS"):
            transistor_type = "NMOS"    

        elif model.upper().startswith("PMOS"):
            transistor_type = "PMOS"    

        else:
            raise ValueError(
                f"Unknown transistor model '{model}' in line:\n{line}"
                )

        width = None
        length = None

        for token in tokens[6:]:
            if token.startswith("W="):
                width = float(token[2:-1])
            elif token.startswith("L="):
                length = float(token[2:-1])

        drain = self._get_or_create_net(cell, drain_name)
        gate = self._get_or_create_net(cell, gate_name)
        source = self._get_or_create_net(cell, source_name)
        bulk = self._get_or_create_net(cell, bulk_name) 

        transistor = Transistor(
            name=name,
            transistor_type=transistor_type,
            model=model,
            drain=drain,
            gate=gate,      
            source=source,
            bulk=bulk,
            width=width,
            length=length
        )

        cell.add_transistor(transistor)
        drain.add_transistor(transistor)
        gate.add_transistor(transistor)
        source.add_transistor(transistor)
        bulk.add_transistor(transistor)

        return transistor
