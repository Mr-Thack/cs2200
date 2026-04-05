import hashlib
import time
import base64
import json
from dataclasses import dataclass
from typing import Optional, List

# ==========================================
# DATA MODELS
# ==========================================

@dataclass
class Wire:
    """
    Represents a connection tunnel. 
    If label is None, it acts as a 'dummy' wire (used for dropping bits in a splitter).
    """
    label: Optional[str]
    bitsize: int


class CircuitBuilder:
    def __init__(self, version="1.11.2-CE"):
        self.version = version
        self.global_bit_size = 1
        self.clock_speed = 1
        self.components = []
        self.wires = []

    def _add_raw_component(self, name: str, x: int, y: int, properties: dict):
        """Internal helper to push components to the JSON array."""
        self.components.append({
            "name": name,
            "x": x,
            "y": y,
            "properties": properties
        })

    def add_tunnel(self, x: int, y: int, direction: str, wire: Optional[Wire]):
        """Spawns a precisely sized tunnel. Skips if the wire or label is None."""
        if not wire or not wire.label:
            return

        # Vertical tunnels need Width 5 to align pins properly
        width = "5" if direction in ["NORTH", "SOUTH"] else "4"

        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.wiring.Tunnel", x, y,
            {
                "Label": wire.label,
                "Direction": direction,
                "Width": width,
                "Bitsize": str(wire.bitsize)
            }
        )

    # ==========================================
    # COMPONENT "BLOCK" GENERATORS
    # ==========================================

    def add_arithmetic(self, peer_type: str, x: int, y: int, in_a: Wire, in_b: Wire, out: Wire, cin: Optional[Wire] = None, cout: Optional[Wire] = None):
        """Handles Adder, Subtractor, Multiplier, Divider, Shifter."""
        self._add_raw_component(
            f"com.ra4king.circuitsim.gui.peers.arithmetic.{peer_type}", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Bitsize": str(out.bitsize)
            }
        )
        self.add_tunnel(x - 6, y,     "EAST",  in_a)
        self.add_tunnel(x - 6, y + 2, "EAST",  in_b)
        self.add_tunnel(x + 4, y + 1, "WEST",  out)
        self.add_tunnel(x - 1, y - 3, "SOUTH", cin)
        self.add_tunnel(x - 1, y + 4, "NORTH", cout)

    def add_comparator(self, x: int, y: int, in_a: Wire, in_b: Wire, out_less: Optional[Wire] = None, out_eq: Optional[Wire] = None, out_greater: Optional[Wire] = None):
        """Special generator for the Comparator's 3 distinct 1-bit outputs."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.arithmetic.ComparatorPeer", x, y,
            {
                "Comparison Type": "2's complement", 
                "Label location": "NORTH", 
                "Label": "", 
                "Bitsize": str(in_a.bitsize)
            }
        )
        self.add_tunnel(x - 6, y,     "EAST", in_a)
        self.add_tunnel(x - 6, y + 2, "EAST", in_b)
        self.add_tunnel(x + 4, y,     "WEST", out_less)    
        self.add_tunnel(x + 4, y + 1, "WEST", out_eq)      
        self.add_tunnel(x + 4, y + 2, "WEST", out_greater) 

    def add_logic_gate(self, gate_type: str, x: int, y: int, in_a: Wire, in_b: Wire, out: Wire):
        """Handles And, Or, Nand, Nor, Xor, Xnor."""
        self._add_raw_component(
            f"com.ra4king.circuitsim.gui.peers.gates.{gate_type}GatePeer", x, y,
            {
                "Negate 0": "No",
                "Negate 1": "No",
                "Number of Inputs": "2", 
                "Label location": "NORTH",
                "Label": "",
                "Direction": "EAST",
                "Bitsize": str(out.bitsize)
            }
        )
        self.add_tunnel(x - 6, y,     "EAST", in_a)
        self.add_tunnel(x - 6, y + 2, "EAST", in_b)
        self.add_tunnel(x + 4, y + 1, "WEST", out)

    def add_not_gate(self, x: int, y: int, in_a: Wire, out: Wire):
        """NOT Gate has a smaller physical footprint."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.gates.NotGatePeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Direction": "EAST",
                "Bitsize": str(out.bitsize)
            }
        )
        self.add_tunnel(x - 6, y, "EAST", in_a)
        self.add_tunnel(x + 3, y, "WEST", out)

    def add_register(self, x: int, y: int, in_d: Wire, out_q: Wire, in_en: Optional[Wire] = None, in_clk: Optional[Wire] = None, in_clr: Optional[Wire] = None):
        """Standard D-Flip-Flop Register."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.RegisterPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Bitsize": str(out_q.bitsize)
            }
        )
        self.add_tunnel(x - 6, y + 1, "EAST",  in_d)
        self.add_tunnel(x - 6, y + 2, "EAST",  in_en)
        self.add_tunnel(x + 4, y + 1, "WEST",  out_q)
        self.add_tunnel(x - 1, y + 4, "NORTH", in_clk)
        self.add_tunnel(x + 1, y + 4, "NORTH", in_clr)

    def add_splitter(self, x: int, y: int, in_bus: Wire, out_wires: List[Wire]):
        """
        Dynamically builds a Splitter. Supports multi-bit outputs and pseudo/dummy 
        wires to drop bits cleanly.
        """
        # 1. Validation: Ensure bits sum perfectly
        total_out_bits = sum(w.bitsize for w in out_wires)
        if total_out_bits != in_bus.bitsize:
            raise ValueError(f"Splitter Mismatch! Input bus is {in_bus.bitsize} bits, but outputs sum to {total_out_bits} bits.")

        fanouts = len(out_wires)
        props = {
            "Fanouts": str(fanouts),
            "Bitsize": str(in_bus.bitsize),
            "Input location": "Left/Top",
            "Direction": "EAST",
            "Label location": "NORTH",
            "Label": ""
        }

        # 2. Map physical bits to logical fanouts
        current_bit = 0
        for fanout_idx, wire in enumerate(out_wires):
            # Assign 'wire.bitsize' number of physical bits to this specific fanout
            for _ in range(wire.bitsize):
                props[f"Bit {current_bit}"] = str(fanout_idx)
                current_bit += 1

            # Place the output tunnel (skips if label is None)
            self.add_tunnel(x + 2, y + fanouts - fanout_idx, "WEST", wire)

        self._add_raw_component("com.ra4king.circuitsim.gui.peers.wiring.SplitterPeer", x, y, props)

        # 3. Place the main bus input tunnel
        self.add_tunnel(x - 6, y - 1, "EAST", in_bus)

    # ==========================================
    # CRYPTOGRAPHY & SAVING
    # ==========================================

    def _sha256ify(self, input_string: str) -> str:
        return hashlib.sha256(input_string.encode('utf-8')).hexdigest()

    def _generate_signature(self, circuits_dict: list) -> str:
        json_str = json.dumps(circuits_dict, indent=2)
        file_data = "null" + json_str.replace('\r\n', '\n')
        file_data_hash = self._sha256ify(file_data)
        timestamp = str(int(time.time() * 1000))
        raw_block_string = "" + file_data_hash + timestamp + ""
        current_hash = self._sha256ify(raw_block_string)
        final_string = f"\t{current_hash}\t{timestamp}\t{file_data_hash}"
        return base64.b64encode(final_string.encode('utf-8')).decode('utf-8')

    def save(self, filename: str):
        circuits_list = [{
            "name": "CircuitMain",
            "components": self.components,
            "wires": self.wires
        }]
        signature = self._generate_signature(circuits_list)
        final_output = {
            "version": self.version,
            "globalBitSize": self.global_bit_size,
            "clockSpeed": self.clock_speed,
            "circuits": circuits_list,
            "revisionSignatures": [signature]
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2)
        print(f"[*] Success: Compiled {len(self.components)} components to {filename}")


# ==========================================
# EXECUTION / TESTING
# ==========================================
if __name__ == "__main__":
    compiler = CircuitBuilder()

    # 1. Spawn a 32-bit Register
    compiler.add_register(
        x=20, y=20, 
        in_d=Wire("W_D_IN", 32), 
        out_q=Wire("W_REGO", 32), 
        in_en=Wire("W__EN_", 1), 
        in_clk=Wire("W__CLK", 1)
    )

    # 2. Add 1 to the Register output
    compiler.add_arithmetic(
        peer_type="AdderPeer", 
        x=20, y=40, 
        in_a=Wire("W_REGO", 32), 
        in_b=Wire("W_CNST", 32), 
        out=Wire("W_ADDO", 32)
    )

    # 3. THE SPLITTER TEST
    # We take the 32-bit output from the Adder and slice it up like an Instruction Decoder!
    # Opcode (6 bits), RegA (5 bits), RegB (5 bits), Ignored (16 bits)
    compiler.add_splitter(
        x=20, y=60, 
        in_bus=Wire("W_ADDO", 32),
        out_wires=[
            Wire("W_OPCD", 6),  # Fanout 0: Gets bits 0-5
            Wire("W_REGA", 5),  # Fanout 1: Gets bits 6-10
            Wire("W_REGB", 5),  # Fanout 2: Gets bits 11-15
            Wire(None, 16)      # Fanout 3: Gets bits 16-31, but drops NO tunnel on canvas!
        ]
    )

    # Save to file
    compiler.save("testing.sim")
