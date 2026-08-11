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
        bulk,
        width,
        length,
    ):
        self.name = name
        self.type = transistor_type
        self.model = model
        self.drain = drain
        self.gate = gate
        self.source = source
        self.bulk = bulk

        self.width = width
        self.length = length

    def __str__(self):
        return (
            f"{self.name} ({self.type})\n"
            f"  D={self.drain.name}\n"
            f"  G={self.gate.name}\n"
            f"  S={self.source.name}\n"
            f"  B={self.bulk.name}\n"
            f"  W={self.width}\n"
            f"  L={self.length}"
        )