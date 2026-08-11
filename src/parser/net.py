class Net:
    """
    Represents one electrical net.
    """

    def __init__(self, name, net_type):
        self.name = name
        self.net_type = net_type

        self.connected_transistors = {}

    def add_transistor(self, transistor):
        self.connected_transistors[transistor.name] = transistor

    def __str__(self):
        return f"{self.name} ({self.net_type})"