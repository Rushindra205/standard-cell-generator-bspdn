class Transistor:
    """
    Represents one MOS transistor.
    """

    def __init__(
        self,
        name,
        transistor_type,
        model,
        drain,
        gate,
        source,
        width=None,
        length=None,
        multiplicity=1,
        wgaa=None,
    ):
        self.name = name
        self.type = transistor_type
        self.model = model
        self.drain = drain
        self.gate = gate
        self.source = source
        
        self.width = width
        self.length = length
        self.multiplicity = multiplicity
        self.wgaa = wgaa

    def __str__(self):
        return (
            f"{self.name} ({self.type})\n"
            f"  D={self.drain.name}\n"
            f"  G={self.gate.name}\n"
            f"  S={self.source.name}\n"
            f"  WGAA={self.wgaa}\n"
            f"  L={self.length}\n"
            f"  M={self.multiplicity}\n"
        )