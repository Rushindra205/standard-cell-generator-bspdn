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
        target_name = f"gt3_6t_{cell_name}_rvt"

        with open(self.filepath, "r", encoding="latin-1") as file:

            for line in file:

                line = line.strip()

                if line.upper().startswith(".SUBCKT"):

                    tokens = line.split()

                    if len(tokens) >= 2 and tokens[1] == target_name:

                        cell = Cell(tokens[1])

                        for line in file:

                            line = line.strip()

                            if line.upper().startswith("*.PININFO"):
                                self._parse_pininfo(line, cell)

                            elif line.upper().startswith("M"):
                                self._parse_transistor(line, cell)

                            elif line.upper().startswith(".ENDS"):
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
            elif name.lower() == "vdd":
                net_type = "POWER"
            elif name.lower() == "vss":
                net_type = "GROUND"
            else:
                net_type = "UNKNOWN"  # Skip unknown pin types

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
        
        model = tokens[4]

        if model.upper().startswith("NMOS"):
            transistor_type = "NMOS"    

        elif model.upper().startswith("PMOS"):
            transistor_type = "PMOS"    

        else:
            raise ValueError(
                f"Unknown transistor model '{model}' in line:\n{line}"
                )

        wgaa = None
        length = None
        multiplicity = 1

        for token in tokens[5:]:

            key, value = token.split("=", 1)

            value = value.rstrip("uU")

            if key.upper() == "WGAA":
                wgaa = float(value)

            elif key.upper() == "L":
                length = float(value)

            elif key.upper() == "M":
                multiplicity = int(value)   
            
            
        drain = self._get_or_create_net(cell, drain_name)
        gate = self._get_or_create_net(cell, gate_name)
        source = self._get_or_create_net(cell, source_name)
         

        transistor = Transistor(
            name=name,
            transistor_type=transistor_type,
            model=model,
            drain=drain,
            gate=gate,      
            source=source,
            length=length,
            multiplicity=multiplicity,
            wgaa=wgaa,
        )

        cell.add_transistor(transistor)
        drain.add_transistor(transistor)
        gate.add_transistor(transistor)
        source.add_transistor(transistor)
        
        return transistor
