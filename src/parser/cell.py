class Cell:
    """
    Represents one standard cell.
    """

    def __init__(self, name):

        self.name = name

        # Dictionaries

        self.transistors = {}

        self.nets = {}

        self.input_nets = {}

        self.output_nets = {}

        self.power_nets = {}

        self.ground_nets = {}

        self.instances = {}

    def add_transistor(self, transistor):
        self.transistors[transistor.name] = transistor

    def add_instance(self, instance):
        self.instances[instance.name] = instance

    def __str__(self):

        s = ""

        s += f"Cell: {self.name}\n"

        s += "Inputs:\n"

        for net in self.input_nets.values():
            s += f"  {net.name}\n"

        s += "Outputs:\n"

        for net in self.output_nets.values():
            s += f"  {net.name}\n"

        s += "Power:\n"

        for net in self.power_nets.values():
            s += f"  {net.name}\n"

        s += "Ground:\n"

        for net in self.ground_nets.values():
            s += f"  {net.name}\n"

        s += f"\nTotal Nets: {len(self.nets)}\n"

        s += f"\n Transistors:\n"

        for transistor in self.transistors.values():
            s += f"{transistor}\n"

        s += f"\nTotal Transistors: {len(self.transistors)}\n"

        s += "\nInstances:\n"

        for instance in self.instances.values():    
            s += f"{instance}\n"

        s += f"\nTotal Instances: {len(self.instances)}\n"


        return s

    def add_net(self,net):
        self.nets[net.name] = net

        if net.net_type == "INPUT":
            self.input_nets[net.name] = net
        elif net.net_type == "OUTPUT":
            self.output_nets[net.name] = net
        elif net.net_type == "POWER":
            self.power_nets[net.name] = net
        elif net.net_type == "GROUND":
            self.ground_nets[net.name] = net

