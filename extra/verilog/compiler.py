import hashlib
import time
import base64
import json
from dataclasses import dataclass
from typing import Optional, List
import math
from collections import Counter
import re
import sys

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
    const_val: str = ""


class CircuitBuilder:
    def __init__(self, version="1.11.2-CE"):
        self.version = version
        self.global_bit_size = 1
        self.clock_speed = 16384

        self.circuits = {}

    def set_active_circuit(self, name: str):
        """Switches the active drawing context to the specified circuit."""
        self.active_circuit = name
        if name not in self.circuits:
            self.circuits[name] = {"components": [], "wires": []}

    def _add_raw_component(self, name: str, x: int, y: int, properties: dict):
        """Internal helper to push components to the JSON array."""
        label = properties.get('Label')
        if (label == None or label == ""):
            properties['Label'] = "CELL " + str(len(self.circuits[self.active_circuit]["components"]))

        self.circuits[self.active_circuit]["components"].append({
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
    # MEMORY ENCODING
    # ==========================================

    @staticmethod
    def encode_rom_contents(data: List[int], data_bits: int) -> str:
        """
        Compresses an array of integers into CircuitSim's Run-Length Encoded Hex format.
        Matches the Java `PropertyMemoryValidator` perfectly.
        """
        if not data:
            return ""

        # Calculate required hex length based on bitsize (e.g. 32 bits = 8 hex chars)
        hex_len = 1 + (data_bits - 1) // 4

        def fmt(val):
            # Mask the value to the correct bit width and format as padded hex
            val = val & ((1 << data_bits) - 1)
            return f"{val:0{hex_len}x}"

        encoded = []
        current_val = data[0]
        count = 1

        for val in data[1:]:
            if val == current_val:
                count += 1
            else:
                encoded.append(f"{count}-{fmt(current_val)}" if count > 1 else fmt(current_val))
                current_val = val
                count = 1

        # Append the final run
        encoded.append(f"{count}-{fmt(current_val)}" if count > 1 else fmt(current_val))

        return " ".join(encoded)

    # ==========================================
    # COMPONENT "BLOCK" GENERATORS
    # ==========================================

    def add_subcircuit(self, x: int, y: int, subcircuit_name: str, in_wires: List[Wire], out_wires: List[Wire]):
        """Creates a Subcircuit Component and hooks up the input/output tunnels."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.SubcircuitPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Subcircuit": subcircuit_name
            }
        )

        # Connect input wires (offset to the left side)
        for i, wire in enumerate(in_wires):
            self.add_tunnel(x - 6, y + i, "EAST", wire)

        # Connect output wires (offset to the right side)
        for i, wire in enumerate(out_wires):
            self.add_tunnel(x + 3, y + i, "WEST", wire)


    def add_ram(self, x: int, y: int, addr_bits: int, data_bits: int,
                in_addr: Wire, in_data: Wire, out_data: Wire, in_clk: Wire,
                in_en: Wire, in_ld: Wire, in_str: Wire, in_clr: Wire,
                label: str = ""):
        """Standard RAM block (Separate Load/Store Ports Active)"""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.RAMPeer", x, y,
            {
                "Separate Load/Store Ports?": "Yes",
                "Label location": "NORTH",
                "Label": label,
                "Bitsize": str(data_bits),
                "Address bits": str(addr_bits)
            }
        )

        # Address
        self.add_tunnel(x - 6, y + 1, "EAST",  in_addr)
        # D_IN
        self.add_tunnel(x - 6, y + 3, "EAST",  in_data)

        # D_OUT
        self.add_tunnel(x + 9, y + 1, "WEST",  out_data)

        # Clock
        self.add_tunnel(x,     y + 5, "NORTH", in_clk)
        # Enable
        self.add_tunnel(x + 1, y + 5, "NORTH", in_en)
        # LD (Load / Read Enable)
        self.add_tunnel(x + 2, y + 5, "NORTH", in_ld)
        # STR (Str / Write Enable)
        self.add_tunnel(x + 3, y + 5, "NORTH", in_str)
        # RESET (Reset / Clear)
        self.add_tunnel(x + 4, y + 5, "NORTH", in_clr)

    def add_rom(self, x: int, y: int, addr_bits: int, contents_array: List[int], 
                in_addr: Wire, out_data: Wire, in_en: Optional[Wire] = None):
        """Standard ROM Block initialized with an array of integers"""
        encoded_string = self.encode_rom_contents(contents_array, out_data.bitsize)

        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.ROMPeer", x, y,
            {
                "Label location": "NORTH",
                "Contents": encoded_string,
                "Label": "",
                "Bitsize": str(out_data.bitsize),
                "Address bits": str(addr_bits)
            }
        )
        self.add_tunnel(x - 6, y + 1, "EAST",  in_addr)
        self.add_tunnel(x + 9, y + 1, "WEST",  out_data)
        self.add_tunnel(x + 1, y + 5, "NORTH", in_en)

    def add_clock(self, x: int, y: int, out_wire: Wire):
        """Spawns a CircuitSim ClockPeer."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.wiring.ClockPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "CLK",
                "Direction": "EAST"
            }
        )
        self.add_tunnel(x + 2, y, "WEST", out_wire)

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

        if cin is None:
            print("[!] POTENTIAL ERROR: Adder cell requires a cin (even set to constant 0) or else output is floating")

        self.add_tunnel(x - 6, y,     "EAST",  in_a)
        self.add_tunnel(x - 6, y + 2, "EAST",  in_b)
        self.add_tunnel(x + 4, y + 1, "WEST",  out)
        self.add_tunnel(x - 1, y - 3, "SOUTH", cin)
        self.add_tunnel(x - 1, y + 4, "NORTH", cout)

    def add_negator(self, x: int, y: int, in_a: Wire, out: Wire):
        """Spawns a Two's Complement Negator (-A) Component."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.arithmetic.NegatorPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Bitsize": str(out.bitsize)
            }
        )

        # Input pin (A) on the left, Output pin (Y) on the right
        self.add_tunnel(x - 6, y + 1, "EAST", in_a)
        self.add_tunnel(x + 4, y + 1, "WEST", out)

    def add_shifter(self, x: int, y: int, in_a: Wire, in_b: Wire, out: Wire, shift_type: str):
        """Handles Shifter operations (LOGICAL LEFT, LOGICAL RIGHT, ARITHMETIC RIGHT)."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.arithmetic.ShifterPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Bitsize": str(out.bitsize),
                "Shift Type": shift_type
            }
        )
        self.add_tunnel(x - 6, y,     "EAST",  in_a)
        self.add_tunnel(x - 6, y + 2, "EAST",  in_b)
        self.add_tunnel(x + 4, y + 1, "WEST",  out)

    def add_comparator(self, x: int, y: int, in_a: Wire, in_b: Wire,
                       out_less: Optional[Wire] = None,
                       out_eq: Optional[Wire] = None,
                       out_greater: Optional[Wire] = None,
                       is_unsigned: bool = False):
        """Special generator for the Comparator's 3 distinct 1-bit outputs."""
        comp_type = "Unsigned" if is_unsigned else "2's complement"
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.arithmetic.ComparatorPeer", x, y,
            {
                "Comparison Type": comp_type, 
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

    def add_multi_logic_gate(self, gate_type: str, x: int, y: int, in_wires: List[Wire], out: Wire):
        """
        Dynamically sized logic gate (And, Or, Nand, Nor, Xor, Xnor).
        Accepts a variable number of input wires.
        """
        num_inputs = len(in_wires)

        # Base properties
        properties = {
            "Number of Inputs": str(num_inputs),
            "Label location": "NORTH",
            "Label": "",
            "Direction": "EAST",
            "Bitsize": str(out.bitsize)
        }

        # CircuitSim expects a "Negate X" property for every single input pin
        for i in range(num_inputs):
            properties[f"Negate {i}"] = "No"

        self._add_raw_component(
            f"com.ra4king.circuitsim.gui.peers.gates.{gate_type}GatePeer",
            x, y + (num_inputs // 2) - 1,
            properties
        )

        # Map input tunnels dynamically along the Y-axis
        for i, in_w in enumerate(in_wires):
            if (i == num_inputs / 2):
                i += 1
            self.add_tunnel(x - 6, y + i, "EAST", in_w)

        # The output pin is dynamically centered based on the number of inputs
        self.add_tunnel(x + 4 + (1 if num_inputs > 5 else 0), y + (num_inputs // 2), "WEST", out)

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

    def add_bit_extender(self, x: int, y: int, in_wire: Wire, out_wire: Wire, is_signed: bool = False):
        """Spawns a Bit Extender component to match CircuitSim's rigid port width rules."""
        ext_type = "SIGN" if is_signed else "ZERO"
        # There's also a "ONE" Extension, but I don't think we'll be needing that
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.arithmetic.BitExtenderPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Direction": "EAST",
                "Input Bitsize": str(in_wire.bitsize),
                "Output Bitsize": str(out_wire.bitsize),
                "Extension Type": ext_type
            }
        )
        self.add_tunnel(x - 6, y + 1, "EAST", in_wire)
        self.add_tunnel(x + 4, y + 1, "WEST", out_wire)
    
    def add_buffer(self, x: int, y: int, in_a: Wire, out: Wire, in_en: Wire):
        """Buffer"""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.gates.ControlledBufferPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Direction": "EAST",
                "Bitsize": str(out.bitsize)
            }
        )
        self.add_tunnel(x - 6, y, "EAST", in_a)
        self.add_tunnel(x - 2, y + 2, "NORTH", in_en)
        self.add_tunnel(x + 3, y, "WEST", out)

    def add_register(self, x: int, y: int, in_d: Wire, out_q: Wire,
                     in_en: Optional[Wire] = None, in_clk: Optional[Wire] = None,
                     in_clr: Optional[Wire] = None, label: str = "", bitsize: int = None):
        """Standard D-Flip-Flop Register."""
        
        REGISTERS = ["zero", "at", "v0", "a0", "a1", "a2", "t0", "t1", "t2", "s0", "s1", "s2", "k0", "sp", "fp", "ra"]
        if ("reg_" in label):
            label = label.replace("reg_", "")

        if ("registers[" in label):
            label = label.replace("registers[", "").replace("]", "")
            label = REGISTERS[int(label)]

        if (label in REGISTERS): 
            label = "$" + label

        label = "PC-IF" if (label in ["PC", "fbuf_out_pc_plus_1"]) else label

        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.RegisterPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": label,
                "Bitsize": str(bitsize or out_q.bitsize)
            }
        )
        # Left
        self.add_tunnel(x - 6, y + 1, "EAST",  in_d)
        if in_en and in_en.const_val != "1":
            self.add_tunnel(x - 6, y + 2, "EAST",  in_en)

        # Right (Output)
        self.add_tunnel(x + 4, y + 1, "WEST",  out_q)

        # Bottom (CLK & CLR)
        self.add_tunnel(x - 2, y + 4, "NORTH", in_clk)

        if in_clr and in_clr.const_val != "0":
            self.add_tunnel(x, y + 4, "NORTH", in_clr)

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

    def add_mux(self, x: int, y: int, sel_bits: int, in_wires: List[Wire], in_sel: Wire, out: Wire):
        """
        Dynamically sized Multiplexer based on coordinate geometry mapped from JSON.
        sel_bits: 1 to 8. in_wires length must be 2^sel_bits.
        """
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.plexers.MultiplexerPeer", x, y,
            {
                "Selector location": "Right/Down",
                "Label location": "NORTH",
                "Selector bits": str(sel_bits),
                "Label": "",
                "Direction": "EAST",
                "Bitsize": str(out.bitsize)
            }
        )

        num_inputs = 2 ** sel_bits
        for i, in_w in enumerate(in_wires):
            self.add_tunnel(x - 6, y + i, "EAST", in_w)

        # The output pin is dynamically centered
        self.add_tunnel(x + 3, y + (num_inputs // 2), "WEST", out)
        # The selector pin dynamically drops below the bottom input
        self.add_tunnel(x - 2, y + num_inputs + 2, "NORTH", in_sel)

    

    def _get_io_offsets(self, bitsize: int, is_output: bool = False):
        """
        Calculates the physical (dx, dy) offsets for pins and constants.
        CircuitSim wraps hex text every 8 bits, expanding the component bounding box.
        """

        dx = 0
        dy = 0

        # Y Offset: connection port shifts down as lines wrap
        if bitsize <= 16:
            dy = 0
        elif bitsize <= 24:
            dy = 1
        else:
            dy = 2

        # X Offset: Output pins anchor on the right, so left-port dx is constant.
        # But it acts weird on output pins less than 8 bits
        # Input pins/Constants anchor on the left, so right-port dx grows with text width.
        if is_output:
            dx = -6
        else:
            dx = 8 
            # This part calculates offset due to line size
            # whereas the previous one calculated offset due to height
            if bitsize < 8:
                offset = bitsize - 8
                
                if bitsize == 1:
                    offset += 1 

                dx += offset

        return dx, dy

    def add_constant(self, x: int, y: int, out: Wire, value: str):
        """Constant value. Output tunnel is placed 8 units to the right."""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.wiring.ConstantPeer", x, y,
            {
                "Label location": "NORTH",
                "Label": "",
                "Value": value,
                "Direction": "EAST",
                "Bitsize": str(out.bitsize),
                "Base": "BINARY"
            }
        )
        dx, dy = self._get_io_offsets(out.bitsize, is_output=False)
        self.add_tunnel(x + dx, y + dy, "WEST", out)

    def add_pin(self, x: int, y: int, wire: Wire, pin_label: str, is_input: bool = True):
        """Standard Input or Output Pin (For top-level CPU I/O)."""
        direction = "EAST" if is_input else "WEST"
        label_loc = "WEST" if is_input else "EAST"
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.wiring.PinPeer", x, y,
            {
                "Label location": label_loc,
                "Label": pin_label,
                "Is input?": "Yes" if is_input else "No",
                "Direction": direction,
                "Bitsize": str(wire.bitsize)
            }
        )


        dx, dy = self._get_io_offsets(wire.bitsize, is_output=not is_input)

        self.add_tunnel(x + dx, y + dy, "WEST" if is_input else "EAST", wire)

    # ==========================================
    # CRYPTOGRAPHY & SAVING
    # ==========================================

    def _sha256ify(self, input_string: str) -> str:
        return hashlib.sha256(input_string.encode('utf-8')).hexdigest()

    def _generate_signature(self, circuits_dict: list) -> str:

        json_str = json.dumps(circuits_dict, indent=2).replace("'", "\\u0027")

        file_data = "null" + json_str.replace('\r\n', '\n')
        # print("File Data:")
        # print(file_data)

        file_data_hash = self._sha256ify(file_data)
        print("File Data Hash:", file_data_hash)

        timestamp = str(int(time.time() * 1000))

        raw_block_string = "" + file_data_hash + timestamp + ""
        print("Block Metadata:", raw_block_string)

        current_hash = self._sha256ify(raw_block_string)
        print("Block Metadata Hash:", current_hash)

        final_string = f"\t{current_hash}\t{timestamp}\t{file_data_hash}"
        print("Final String:", final_string)

        signature = base64.b64encode(final_string.encode('utf-8')).decode('utf-8')
        print("Signature:", signature)

        return signature

    def _remap_labels(self):
        """
        Passes over all components in ALL circuits and replaces verbose wire labels 
        with guaranteed 6-character labels (e.g., T_0000, C_0000)
        """
        label_map = {}
        wire_counter = 0
        const_counter = 0

        for circ_name, circ_data in self.circuits.items():
            for comp in circ_data["components"]:
                props = comp.get("properties", {})

                # Tunnels and Pins use the "Label" property
                if "Label" in props and props["Label"]:
                    old_label = props["Label"]

                    # Fixed prefix check: get_wire outputs W_, not WIRE_
                    if old_label.startswith(("W_", "CONST_", "PMUX_", "L_AND_", "L_OR_")):
                        if old_label not in label_map:
                            if old_label.startswith("CONST_"):
                                label_map[old_label] = f"C_{const_counter:04X}"
                                const_counter += 1
                            else:
                                label_map[old_label] = f"T_{wire_counter:04X}"
                                wire_counter += 1

                        props["Label"] = label_map[old_label]

    def optimize_tunnel_clusters(self, max_fanout=8):
        """
        Builds a Fractal Tree of Tunnels to strictly cap fanout.
        No label will EVER appear more than `max_fanout` + 1 times.
        This drops the O(N^2) CircuitSim lag to near absolute zero.
        """
        hex_counter = 0

        def get_label(prefix):
            nonlocal hex_counter
            lbl = f"{prefix}_{hex_counter:04X}"
            hex_counter += 1
            return lbl

        for circ_name, circ_data in self.circuits.items():
            # 1. Collect all Tunnel components
            tunnel_comps = [c for c in circ_data["components"] if "Tunnel" in c["name"]]

            # Group by current label
            label_groups = {}
            for c in tunnel_comps:
                lbl = c.get("properties", {}).get("Label", "")
                if lbl:
                    label_groups.setdefault(lbl, []).append(c)

            # Drop location for the bridge tree (far right of canvas)
            bridge_x = 200 
            bridge_y = 50

            # 2. Process each massive label
            for original_label, comps in label_groups.items():
                if len(comps) <= max_fanout:
                    continue

                bitsize = int(comps[0].get("properties", {}).get("Bitsize", "1"))
                prefix = "C" if ("CLK" in original_label.upper() or "CLOCK" in original_label.upper()) else "B"

                # Layer 0: Assign unique labels to the actual components in the circuit
                current_level_labels = []
                for i, c in enumerate(comps):
                    chunk_idx = i // max_fanout
                    if chunk_idx == len(current_level_labels):
                        current_level_labels.append(get_label(prefix))

                    c["properties"]["Label"] = current_level_labels[-1]

                # Layer 1 to N: Build the tree upwards until only 1 root label remains
                self.set_active_circuit(circ_name)

                while len(current_level_labels) > 1:
                    next_level_labels = []

                    for i, child_lbl in enumerate(current_level_labels):
                        parent_chunk_idx = i // max_fanout

                        # Generate a new parent label if we are starting a new chunk
                        if parent_chunk_idx == len(next_level_labels):
                            next_level_labels.append(get_label(prefix))

                        parent_lbl = next_level_labels[-1]

                        # Build the face-to-face bridge (Parent <-connects to-> Child)
                        self.add_tunnel(bridge_x, bridge_y, "EAST", Wire(parent_lbl, bitsize))
                        self.add_tunnel(bridge_x + 6, bridge_y, "WEST", Wire(child_lbl, bitsize))
                        bridge_y += 5

                    current_level_labels = next_level_labels

    def save(self, filename: str, debug_labels: bool = False):
        # Temporarily Disable for debugging
        if not debug_labels:
            self._remap_labels()

        circuits_list = []
        for name, data in self.circuits.items():
            circuits_list.append({
                "name": name,
                "components": data["components"],
                "wires": data["wires"]
            })

        signature = self._generate_signature(circuits_list)

        final_output = {
            "version": self.version,
            "globalBitSize": self.global_bit_size,
            "clockSpeed": self.clock_speed,
            "circuits": circuits_list,
            "revisionSignatures": [signature]
        }

        final_json_str = json.dumps(final_output, indent=2).replace("'", "\\u0027")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(final_json_str)


        total_components = sum(len(c["components"]) for c in self.circuits.values())
        print(f"[*] Success: Compiled {total_components} components across {len(self.circuits)} circuits to {filename}")


    def print_stats(self):
        print("\n" + "="*50)
        print(" 📊 CIRCUIT SIM COMPONENT STATS BREAKDOWN ")
        print("="*50)

        global_counter = Counter()
        tunnel_counter = Counter() # Track tunnel labels globally

        for circ_name, data in self.circuits.items():
            circ_counter = Counter()
            for comp in data["components"]:
                # Clean up the long Java class names
                short_name = comp["name"].split('.')[-1].replace('Peer', '').replace('Gate', ' Gate')
                circ_counter[short_name] += 1
                global_counter[short_name] += 1

                # If it's a Tunnel, tally up its label
                if short_name == "Tunnel":
                    label = comp.get("properties", {}).get("Label", "")
                    if label:
                        tunnel_counter[label] += 1

            print(f"\n--- Module: {circ_name} ---")
            for name, count in circ_counter.most_common():
                print(f"  {name:<15}: {count}")

        print("\n" + "-"*50)
        print(" 🌍 GLOBAL TOTALS ")
        print("-"*50)
        for name, count in global_counter.most_common():
            print(f"  {name:<15}: {count}")

        print("\n" + "-"*50)
        print(" 🕳️ TOP 10 MOST COMMON TUNNELS ")
        print("-"*50)
        # Print the worst offenders
        for label, count in tunnel_counter.most_common(10):
            print(f"  {label:<35}: {count}")
        print("="*50 + "\n")



# ==========================================
# TRANSLATION / COMPILATION LAYER 
# ==========================================

# Global tracker for constants so we can spawn them at the end
GLOBAL_CONSTANTS = {}

def build_bit_registry(module_data, netlist) -> dict:
    """
    Pre-pass scanner: Maps every individual driven bit to its Parent Bus.
    Returns a dict: { bit_id: tuple_of_parent_bits }
    """
    registry = {}

    # 1. Module inputs drive bits into the circuit
    for port_name, port_data in module_data.get("ports", {}).items():
        if port_data.get("direction") == "input":
            bits = tuple(port_data.get("bits", []))
            for b in bits:
                registry[b] = bits

    # 2. Cell outputs drive bits into the circuit
    for cell_name, cell_data in module_data.get("cells", {}).items():
        c_type = cell_data["type"]
        conns = cell_data.get("connections", {})

        # Map standard Yosys primitives to their output ports
        output_ports = []
        if c_type in ["$add", "$sub", "$mul", "$neg",
                      "$not", "$and", "$or", "$xor",
                      "$eq", "$ne", "$gt", "$lt", 
                      "$mux", "$pmux",
                      "$logic_not", "$logic_and", "$logic_or", 
                      "$reduce_or", "$reduce_and", "$reduce_bool",
                      "$shl", "$shr", "$sshl", "$sshr",
                      "$cs_folded_mux"]:
            output_ports = ["Y"]
        elif c_type.startswith("cs_mux_"):
            output_ports = ["y"]
        elif c_type == "cs_register":
            output_ports = ["q"]
        elif c_type == "$cs_mega_comparator":
            # Dynamically grab all output ports we created (Y_EQ, Y_LT, Y_GE, etc.)
            output_ports = [p for p in conns.keys() if p.startswith("Y_")]
        elif c_type in ["$mem", "$mem_v2"]:
            output_ports = ["RD_DATA"]
        elif c_type in ["$dff", "$dffe", "$sdff", "$sdffce", "$sdffe"]:
            output_ports = ["Q"]
        elif c_type == "cs_clock":
            output_ports = "clk"
        elif not c_type.startswith("$") or c_type.startswith("$paramod$"):
            # It's a subcircuit; look up its specific output ports in the netlist
            sub_mod = netlist.get("modules", {}).get(c_type, {})
            for p_name, p_data in sub_mod.get("ports", {}).items():
                if p_data.get("direction") == "output":
                    output_ports.append(p_name)

        # Record the bits driven by these output ports
        for p in output_ports:
            if p in conns:
                bits = tuple(conns[p])
                for b in bits:
                    registry[b] = bits

    return registry

def get_wire(bits_array, current_module_name: str = "Main") -> Wire:
    bitsize = len(bits_array)
    if bitsize == 0:
        return Wire(None, 0)
    
    safe_module_name = current_module_name.split('\\')[-1].replace('$', '')

    if isinstance(bits_array[0], str):
        val_str = "".join(str(b) for b in reversed(bits_array)).replace('x', '0')
        val_hex = f"{int(val_str, 2):X}"
        label = f"CONST_VAL_{val_hex}_BITS_{bitsize}"
        wire = Wire(label, bitsize, val_str)

        if safe_module_name not in GLOBAL_CONSTANTS:
            GLOBAL_CONSTANTS[safe_module_name] = {}

        GLOBAL_CONSTANTS[safe_module_name][label] = {"wire": wire, "val": val_str}
        return wire

    # Create a unique string out of the exact bit array and module scope
    # e.g., "mem_5_6_7_8"
    bit_str = "_".join(str(b) for b in bits_array)
    unique_id = f"W_{safe_module_name}_{bit_str}"

    return Wire(unique_id, bitsize)

def build_master_splitters(compiler: CircuitBuilder, grid, module_data: dict, bit_registry: dict, current_module: str):
    """
    Pre-pass: Scans the entire module to find every tap on every bus.
    Creates a single Master Splitter per bus that precisely partitions 
    it into the required non-overlapping segments.
    """
    compiler.parent_segments = {}
    taps_by_parent = {}

    # 1. Collect all requested bit arrays in the entire module
    all_reqs = []
    for port in module_data.get("ports", {}).values():
        all_reqs.append(port.get("bits", []))
    for cell in module_data.get("cells", {}).values():
        for bits in cell.get("connections", {}).values():
            all_reqs.append(bits)

    # 2. Break requests down into contiguous chunks
    for raw_bits in all_reqs:
        if not raw_bits: continue

        # Handle sign extension repeating bits
        repeats = 0
        for i in range(len(raw_bits) - 1, 0, -1):
            if raw_bits[i] == raw_bits[i - 1]: repeats += 1
            else: break
        core_bits = raw_bits[:len(raw_bits)-repeats] if repeats > 0 else raw_bits

        chunks = []
        current_chunk = []
        current_parent = None

        for b in core_bits:
            parent = bit_registry.get(b, "CONSTANT") if isinstance(b, int) else "CONSTANT"
            is_contiguous = False
            if parent != "CONSTANT" and current_parent == parent and current_chunk:
                if parent.index(b) == parent.index(current_chunk[-1]) + 1:
                    is_contiguous = True

            if parent == current_parent and (parent == "CONSTANT" or is_contiguous):
                current_chunk.append(b)
            else:
                if current_chunk: chunks.append((current_parent, current_chunk))
                current_chunk = [b]
                current_parent = parent

        if current_chunk: chunks.append((current_parent, current_chunk))

        # Only care about actual sub-slices (taps)
        for parent, chunk in chunks:
            if parent != "CONSTANT" and len(chunk) < len(parent):
                taps_by_parent.setdefault(parent, []).append(chunk)

    # 3. Calculate Boundaries and build the Master Splitters
    for parent, chunks in taps_by_parent.items():
        parent_tuple = tuple(parent)
        boundaries = {0, len(parent)}
        for chunk in chunks:
            start_idx = parent.index(chunk[0])
            boundaries.add(start_idx)
            boundaries.add(start_idx + len(chunk))

        sorted_bounds = sorted(list(boundaries))
        if len(sorted_bounds) <= 2: continue # Used whole; no splitter needed!

        out_wires = []
        segment_dict = {}

        # Build the exact partitions
        for i in range(len(sorted_bounds) - 1):
            start = sorted_bounds[i]
            end = sorted_bounds[i+1]
            seg_chunk = parent[start:end]

            # Check if this segment falls inside any requested chunk
            is_needed = any(start >= parent.index(c[0]) and end <= (parent.index(c[0]) + len(c)) for c in chunks)

            if is_needed:
                wire = Wire(f"W_SEG_{seg_chunk[0]}_to_{seg_chunk[-1]}_{grid.x}_{grid.y}", end - start)
                segment_dict[(start, end)] = wire
                out_wires.append(wire)
            else:
                # Unused bits get routed to a Dummy/Null wire
                out_wires.append(Wire(None, end - start))

        # Spawn the Master Splitter!
        x, y = grid.next()
        compiler.add_splitter(x, y, get_wire(list(parent), current_module), out_wires)
        compiler.parent_segments[parent_tuple] = segment_dict

def resolve_bus(compiler: CircuitBuilder, grid, raw_bits: List[int], current_module: str, bit_registry: dict) -> Wire:
    if not raw_bits:
        return Wire(None, 0)

    # --- MEMOIZATION LAYER ---
    cache_key = tuple(raw_bits)
    if hasattr(compiler, 'resolved_buses') and cache_key in compiler.resolved_buses:
        return compiler.resolved_buses[cache_key]

    def _resolve():
        if all(isinstance(b, str) for b in raw_bits):
            return get_wire(raw_bits, current_module)

        # Sign Extension Trapping
        repeats = 0
        for i in range(len(raw_bits) - 1, 0, -1):
            if raw_bits[i] == raw_bits[i - 1]: repeats += 1
            else: break

        if repeats > 0:
            base_bits = raw_bits[:len(raw_bits)-repeats]
            base_wire = resolve_bus(compiler, grid, base_bits, current_module, bit_registry)
            return get_padded_wire(compiler, grid, base_wire, len(raw_bits), current_module, is_signed=True)

        chunks = []
        current_chunk = []
        current_parent = None

        for b in raw_bits:
            parent = bit_registry.get(b, "CONSTANT") if isinstance(b, int) else "CONSTANT"
            is_contiguous = False
            if parent != "CONSTANT" and current_parent == parent and current_chunk:
                if parent.index(b) == parent.index(current_chunk[-1]) + 1:
                    is_contiguous = True

            if parent == current_parent and (parent == "CONSTANT" or is_contiguous):
                current_chunk.append(b)
            else:
                if current_chunk: chunks.append((current_parent, current_chunk))
                current_chunk = [b]
                current_parent = parent

        if current_chunk: chunks.append((current_parent, current_chunk))

        if len(chunks) == 1:
            parent, chunk = chunks[0]
            if parent == tuple(raw_bits):
                return get_wire(raw_bits, current_module)

        # Assemble the hardware
        chunk_wires = []
        for parent, chunk in chunks:
            if parent == "CONSTANT":
                chunk_wires.append(get_wire(chunk, current_module))
            elif len(chunk) == len(parent):
                chunk_wires.append(get_wire(list(parent), current_module))
            else:
                # Sliced Bus: Tap the Master Splitter segments!
                start_idx = parent.index(chunk[0])
                end_idx = start_idx + len(chunk)
                parent_tuple = tuple(parent)

                # Fetch from our pre-pass dictionary
                if hasattr(compiler, 'parent_segments') and parent_tuple in compiler.parent_segments:
                    sub_segments = []
                    curr_idx = start_idx

                    # Gather the Master Splitter segments that make up this specific chunk
                    while curr_idx < end_idx:
                        for (s_start, s_end), wire in compiler.parent_segments[parent_tuple].items():
                            if s_start == curr_idx:
                                sub_segments.append(wire)
                                curr_idx = s_end
                                break

                    if len(sub_segments) == 1:
                        chunk_wires.append(sub_segments[0])
                    else:
                        # Sometimes a requested slice spans across multiple boundaries 
                        # requested by someone else. We merge them back together here.
                        merged_label = "_".join(str(b) for b in chunk[:3])
                        target_wire = Wire(f"W_REBUILD_{merged_label}_{grid.x}_{grid.y}", len(chunk))
                        x, y = grid.next()
                        compiler.add_splitter(x, y, target_wire, sub_segments)
                        chunk_wires.append(target_wire)
                else:
                    # Fallback (Should rarely hit)
                    out_wires = []
                    if start_idx > 0: out_wires.append(Wire(None, start_idx))
                    tap_wire = Wire(f"W_TAP_{chunk[0]}_to_{chunk[-1]}_{grid.x}_{grid.y}", len(chunk))
                    out_wires.append(tap_wire)
                    if end_idx < len(parent): out_wires.append(Wire(None, len(parent) - end_idx))
                    x, y = grid.next()
                    compiler.add_splitter(x, y, get_wire(list(parent), current_module), out_wires)
                    chunk_wires.append(tap_wire)

        # Merge Multiple Chunks together
        if len(chunk_wires) > 1:
            merged_label = "_".join(str(b) for b in raw_bits[:3])
            target_wire = Wire(f"W_MERGE_{merged_label}_{grid.x}_{grid.y}", len(raw_bits))
            x, y = grid.next()
            compiler.add_splitter(x, y, target_wire, chunk_wires)
            return target_wire

        return chunk_wires[0]

    # Execute, Cache, and Return
    final_wire = _resolve()
    if hasattr(compiler, 'resolved_buses'):
        compiler.resolved_buses[cache_key] = final_wire
    return final_wire



class GridAllocator:
    def __init__(self, x_init, y_init, x_spacing, y_spacing, x_max):
        self.x = x_init
        self.y = y_init
        self.x_init = x_init
        self.x_spacing = x_spacing
        self.y_spacing = y_spacing
        self.x_max = x_max

    def next(self):
        """Returns the next available (x, y) coordinate and advances the internal grid cursor."""
        curr_x, curr_y = self.x, self.y
        self.x += self.x_spacing
        if self.x > self.x_max:
            self.x = self.x_init
            self.y += self.y_spacing
        return curr_x, curr_y


def get_padded_wire(compiler: CircuitBuilder, grid: GridAllocator, original_wire: Wire,
                    target_width: int, current_module: str, is_signed: bool = False) -> Wire:
    """
    Checks if a bit array needs padding. If so, physically spawns a Bit Extender 
    on the canvas to safely bridge the original wire to the required width.
    """
    if not original_wire or original_wire.bitsize == 0:
        return original_wire

    if original_wire.bitsize >= target_width:
        return original_wire

    # We need padding. Create a unique target wire for the padded output.
    padded_label = f"{original_wire.label}_EXT_{target_width}"
    padded_wire = Wire(padded_label, target_width)


    if original_wire.const_val:
        # const_val[0] is the MSB. If signed, copy the MSB. If unsigned, pad with '0'.
        pad_bit = original_wire.const_val[0] if is_signed else '0'
        pad_length = target_width - original_wire.bitsize

        # Prepend the padding to the original binary string
        new_val_str = (pad_bit * pad_length) + original_wire.const_val

        # get_wire expects an LSB-first array of strings, so we reverse it back
        new_bits_array = list(reversed(new_val_str))

        return get_wire(new_bits_array, current_module)
    
    x, y = grid.next()

    # Instruct the compiler to build the physical bridging component
    compiler.add_bit_extender(x, y, original_wire, padded_wire, is_signed)

    # print(f"Adding Padding for {original_wire.label} to {padded_wire.label}")

    return padded_wire

# ========== #
# Optimizers #
# ========== #

def _replace_bit_in_module(mod_data: dict, old_bit: int, new_bit):
    """
    Helper function: Sweeps the entire module and rewires any connection 
    looking for `old_bit` to point to `new_bit` instead.
    """
    # Reroute Ports
    for port in mod_data.get("ports", {}).values():
        port["bits"] = [new_bit if b == old_bit else b for b in port.get("bits", [])]

    # Reroute Cells
    for cell in mod_data.get("cells", {}).values():
        for conn_name, bits in cell.get("connections", {}).items():
            cell["connections"][conn_name] = [new_bit if b == old_bit else b for b in bits]

def optimize_constant_muxes(netlist: dict) -> dict:
    """
    Pre-traversal pass: Finds 1-bit $mux cells operating purely on constants.
    - If 0 / 1: Deletes the MUX and aliases the wire directly.
    - If 1 / 0: Demotes the MUX to a smaller $not gate.
    - If same / same: Deletes the MUX and aliases the wire to the constant.
    """
    for mod_name, mod_data in netlist.get("modules", {}).items():
        cells = mod_data.get("cells", {})
        cells_to_delete = []

        for cell_name, cell_data in cells.items():
            if cell_data.get("type") == "$mux":
                conns = cell_data.get("connections", {})
                a_conn = conns.get("A", [])
                b_conn = conns.get("B", [])
                s_conn = conns.get("S", [])
                y_conn = conns.get("Y", [])

                # Check if it's a 1-bit MUX
                if len(a_conn) == 1 and len(b_conn) == 1 and len(y_conn) == 1:
                    a_val = a_conn[0]
                    b_val = b_conn[0]

                    # Ensure both inputs A and B are hardcoded strings (constants)
                    if isinstance(a_val, str) and isinstance(b_val, str):
                        y_bit = y_conn[0]
                        s_bit = s_conn[0]

                        if a_val == "0" and b_val == "1":
                            # Case 1: Y = S. Bypass MUX entirely!
                            _replace_bit_in_module(mod_data, y_bit, s_bit)
                            cells_to_delete.append(cell_name)

                        elif a_val == "1" and b_val == "0":
                            # Case 2: Y = NOT S. Demote MUX to a NOT gate.
                            cell_data["type"] = "$not"
                            # A NOT gate only takes input "A", so we map the selector to A
                            cell_data["connections"] = {
                                    "A": s_conn,
                                    "Y": y_conn
                                    }
                            # We leave this cell in the dictionary, just mutated

                        elif a_val == b_val: 
                            # Case 3: Both inputs are the same. Y is a constant.
                            _replace_bit_in_module(mod_data, y_bit, a_val)
                            cells_to_delete.append(cell_name)

        # Cleanup: Actually remove the bypassed gates from the JSON tree
        for c in cells_to_delete:
            del cells[c]

    return netlist

def optimize_comparator_groups(netlist: dict) -> dict:
    """
    Pre-traversal pass: Groups $eq, $ne, $lt, $le, $gt, $ge cells that share
    the exact same A and B inputs. Merges them into a single $cs_mega_comparator.
    """
    for mod_name, mod_data in netlist.get("modules", {}).items():
        cells = mod_data.get("cells", {})

        # 1. Signature grouping: (A_bits, B_bits, A_signed, B_signed)
        groups = {}
        for cell_name, cell_data in cells.items():
            c_type = cell_data.get("type")
            if c_type in ["$eq", "$ne", "$lt", "$le", "$gt", "$ge"]:
                conns = cell_data.get("connections", {})
                params = cell_data.get("parameters", {})

                # Tuples make the arrays hashable so they can be dictionary keys
                sig = (
                    tuple(conns.get("A", [])), 
                    tuple(conns.get("B", [])),
                    params.get("A_SIGNED", "0"),
                    params.get("B_SIGNED", "0")
                )

                if sig not in groups:
                    groups[sig] = []
                groups[sig].append((cell_name, c_type, conns.get("Y", [])))

        # 2. Merge groups larger than 1
        for sig, group_cells in groups.items():
            if len(group_cells) > 1:
                a_bits, b_bits, a_signed, b_signed = sig

                mega_name = f"\\MEGA_CMP_{group_cells[0][0]}"
                mega_conns = {"A": list(a_bits), "B": list(b_bits)}

                # Map the old Y outputs to specific ports on the mega comparator
                for c_name, c_type, y_bits in group_cells:
                    port_name = c_type.replace("$", "Y_").upper() # e.g., $eq -> Y_EQ
                    mega_conns[port_name] = y_bits
                    del cells[c_name] # Erase the redundant hardware

                cells[mega_name] = {
                    "type": "$cs_mega_comparator",
                    "parameters": {"A_SIGNED": a_signed, "B_SIGNED": b_signed},
                    "connections": mega_conns
                }

    return netlist

def optimize_1bit_comparators(netlist: dict) -> dict:
    """
    Pre-traversal pass: Finds 1-bit comparators where one input is a constant.
    Demotes the comparator to a wire alias, a constant, or a $not gate.
    """
    for mod_name, mod_data in netlist.get("modules", {}).items():
        cells = mod_data.get("cells", {})
        cells_to_delete = []

        for cell_name, cell_data in cells.items():
            c_type = cell_data.get("type")
            if c_type in ["$eq", "$ne", "$lt", "$le", "$gt", "$ge"]:
                conns = cell_data.get("connections", {})
                a_conn = conns.get("A", [])
                b_conn = conns.get("B", [])
                y_conn = conns.get("Y", [])

                # Must be purely a 1-bit comparison
                if len(a_conn) == 1 and len(b_conn) == 1 and len(y_conn) == 1:
                    params = cell_data.get("parameters", {})
                    a_signed = int(params.get("A_SIGNED", "0"), 2) == 1
                    b_signed = int(params.get("B_SIGNED", "0"), 2) == 1

                    # Safety check: Only optimize unsigned comparisons
                    if a_signed or b_signed:
                        continue

                    a_val = a_conn[0]
                    b_val = b_conn[0]
                    y_bit = y_conn[0]

                    is_a_const = isinstance(a_val, str)
                    is_b_const = isinstance(b_val, str)

                    # If neither are constants, or both are constants, skip.
                    if is_a_const == is_b_const:
                        continue

                    const_val = a_val if is_a_const else b_val
                    wire_bit = b_val if is_a_const else a_val

                    # Map every scenario into an action
                    action = None

                    if is_b_const: 
                        # SCENARIO: (Wire CMP Const)
                        if const_val == "0":
                                if c_type == "$eq": action = "NOT_WIRE"
                                elif c_type == "$ne": action = "ALIAS_WIRE"
                                elif c_type == "$gt": action = "ALIAS_WIRE"
                                elif c_type == "$lt": action = "CONST_0"
                                elif c_type == "$ge": action = "CONST_1"
                                elif c_type == "$le": action = "NOT_WIRE"
                        elif const_val == "1":
                            if c_type == "$eq": action = "ALIAS_WIRE"
                            elif c_type == "$ne": action = "NOT_WIRE"
                            elif c_type == "$gt": action = "CONST_0"
                            elif c_type == "$lt": action = "NOT_WIRE"
                            elif c_type == "$ge": action = "ALIAS_WIRE"
                            elif c_type == "$le": action = "CONST_1"
                    else: 
                        # SCENARIO: (Const CMP Wire)
                        if const_val == "0":
                            if c_type == "$eq": action = "NOT_WIRE"
                            elif c_type == "$ne": action = "ALIAS_WIRE"
                            elif c_type == "$gt": action = "CONST_0"
                            elif c_type == "$lt": action = "ALIAS_WIRE"
                            elif c_type == "$ge": action = "NOT_WIRE"
                            elif c_type == "$le": action = "CONST_1"
                        elif const_val == "1":
                            if c_type == "$eq": action = "ALIAS_WIRE"
                            elif c_type == "$ne": action = "NOT_WIRE"
                            elif c_type == "$gt": action = "NOT_WIRE"
                            elif c_type == "$lt": action = "CONST_0"
                            elif c_type == "$ge": action = "CONST_1"
                            elif c_type == "$le": action = "ALIAS_WIRE"

                    # Execute the determined action
                    if action == "ALIAS_WIRE":
                        _replace_bit_in_module(mod_data, y_bit, wire_bit)
                        cells_to_delete.append(cell_name)
                    elif action == "CONST_0":
                        _replace_bit_in_module(mod_data, y_bit, "0")
                        cells_to_delete.append(cell_name)
                    elif action == "CONST_1":
                        _replace_bit_in_module(mod_data, y_bit, "1")
                        cells_to_delete.append(cell_name)
                    elif action == "NOT_WIRE":
                        # Keep the cell, but overwrite it to be a NOT gate
                        cell_data["type"] = "$not"
                        cell_data["connections"] = {"A": [wire_bit], "Y": [y_bit]}

        # Delete bypassed cells from the JSON dictionary
        for c in cells_to_delete:
            del cells[c]

    return netlist

def optimize_mux_chains(netlist: dict) -> dict:
    """
    Pre-traversal pass: Folds cascading 2-to-1 $mux cells into native 
    CircuitSim Multiplexers. Safely breaks chains into sub-chains if 
    an intermediate value is tapped by side-channel logic.
    """
    for mod_name, mod_data in netlist.get("modules", {}).items():
        cells = mod_data.get("cells", {})

        # 1. Map MUX drivers: Y_tuple -> cell_name
        mux_drivers = {}
        for c_name, c_data in cells.items():
            if c_data.get("type") == "$mux" and len(c_data.get("connections", {}).get("S", [])) == 1:
                mux_drivers[tuple(c_data["connections"]["Y"])] = c_name

        # 2. Track every single bit consumer to detect side-channel taps
        input_consumers = {} # bit -> list of (cell_name, port_name)
        for c_name, c_data in cells.items():
            for port, bits in c_data.get("connections", {}).items():
                if port not in ["Y", "Q", "RD_DATA"]: # It's an input port
                    for b in bits:
                        if isinstance(b, int):
                            input_consumers.setdefault(b, []).append((c_name, port))

        for p_name, p_data in mod_data.get("ports", {}).items():
            if p_data.get("direction") == "output":
                for b in p_data.get("bits", []):
                    if isinstance(b, int):
                        input_consumers.setdefault(b, []).append(("MODULE_OUT", p_name))

        # 3. Determine which MUXes can be safely absorbed
        def is_safely_subsumed(mux_name):
            y_bits = cells[mux_name]["connections"]["Y"]
            consumer_cell = None
            for b in y_bits:
                if not isinstance(b, int): continue # Skip constants
                consumers = input_consumers.get(b, [])

                if len(consumers) != 1: return False # Tapped by multiple gates!

                c_name, c_port = consumers[0]
                if c_port != "A": return False # Tapped by a non-A port!
                if cells.get(c_name, {}).get("type") != "$mux": return False

                if consumer_cell is None: consumer_cell = c_name
                elif consumer_cell != c_name: return False # Bits split across different cells!
            return True

        # 4. Find all "Heads" (MUXes that MUST physically output their Y values)
        all_muxes = list(mux_drivers.values())
        heads = [m for m in all_muxes if not is_safely_subsumed(m)]

        # 5. Build Sub-Chains and Fold
        cells_to_delete = set()
        for head_name in heads:
            if head_name not in cells: continue 

            curr_name = head_name
            chain = [] 

            while curr_name and len(chain) < 5: 
                chain.append((curr_name, cells[curr_name]))
                a_tup = tuple(cells[curr_name]["connections"]["A"])

                driver_name = mux_drivers.get(a_tup)
                # If the driver is safely subsumed, we keep extending the chain!
                if driver_name and is_safely_subsumed(driver_name):
                    curr_name = driver_name
                else:
                    # CHAIN BREAKS! If driver_name is tapped, it acts as the 
                    # Head of its OWN sub-chain. We stop absorbing here.
                    curr_name = None 

            if len(chain) < 2:
                continue 

            chain.reverse() # Tail (lowest priority) at index 0, Head at index -1

            tail_data = chain[0][1]
            head_data = chain[-1][1]

            default_A = tail_data["connections"]["A"]
            y_out = head_data["connections"]["Y"]

            chain_B = [c["connections"]["B"] for name, c in chain]
            chain_S = [c["connections"]["S"][0] for name, c in chain]

            n = len(chain)
            num_inputs = 2 ** n

            flat_data = []
            for i in range(num_inputs):
                val = default_A
                for bit_idx in range(n):
                    if (i & (1 << bit_idx)) != 0:
                        val = chain_B[bit_idx]
                flat_data.extend(val)

            mega_name = f"\\CS_FOLDED_MUX_{head_name}"
            cells[mega_name] = {
                "type": "$cs_folded_mux",
                "connections": {
                    "A": flat_data,  
                    "S": chain_S,    
                    "Y": y_out
                }
            }

            for name, c in chain:
                cells_to_delete.add(name)

        for c in cells_to_delete:
            if c in cells: del cells[c]

    return netlist

def parse_yosys_netlist(compiler: CircuitBuilder, json_file_path: str, OPTIMIZE: bool = True):
    """
    The main compilation loop.
    """
    with open(json_file_path, 'r') as f:
        netlist = json.load(f)

    if OPTIMIZE:
        netlist = optimize_constant_muxes(netlist)
        netlist = optimize_1bit_comparators(netlist)
        netlist = optimize_mux_chains(netlist)
        netlist = optimize_comparator_groups(netlist)

    # with open("pipeline.json", "w") as f:
    #    json.dump(netlist['modules']['pipeline'], f, indent=4)

    X_SPACING = 25 
    Y_SPACING = 50 
    X_INIT = 50
    Y_INIT = 50
    
    PIN_X_INIT = 25
    PIN_Y_INIT = 25

    X_MAX = 100


    for module_name, module_data in netlist.get("modules", {}).items():
        safe_mod_name = module_name.split('\\')[-1].replace('$', '')
        if safe_mod_name.startswith("cs_"):
            # Don't make this one because it's a CircuitSim specific override that we've defined below
            continue

        # Determine if this is the top level module (Fallback to Main)
        if module_data.get("attributes", {}).get("top", 0) == 1:
            safe_mod_name = "Main"

        print(f"[*] Compiling module: {module_name}")

        bit_registry = build_bit_registry(module_data, netlist)

        # Yosys does not assign the name to the register;
        # instead, it assigns the name (in the Verilog) to the output wire
        # But, CircuitSim (or rather the auto grader) wants to see the register
        reverse_netnames = {}
        for net_name, net_data in module_data.get("netnames", {}).items():
            if net_data.get("hide_name", 0) == 0 and not net_name.startswith("$"):
                bits_tuple = tuple(net_data.get("bits", []))
                # Strip the leading backslash Yosys adds to explicit names
                clean_net_name = net_name.lstrip('\\')
                
                # Check for collisions (multiple cables coming from the same thing)
                if bits_tuple in reverse_netnames:
                    # Only write new net name if this one is "simpler"
                    # ddfineed (arbitrarily as not being an array "[")
                    if "[" in reverse_netnames[bits_tuple] and "[" not in clean_net_name:
                        reverse_netnames[bits_tuple] = clean_net_name
                else:
                    reverse_netnames[bits_tuple] = clean_net_name
        # print(reverse_netnames)

        compiler.set_active_circuit(safe_mod_name)
        
        grid = GridAllocator(X_INIT, Y_INIT, X_SPACING, Y_SPACING, X_MAX)

        compiler.resolved_buses = {} # Clear the memoization cache per-module
        build_master_splitters(compiler, grid, module_data, bit_registry, safe_mod_name)

        # Helper for Outputs (Directly defines parent buses)
        def gw(bits): return get_wire(bits, safe_mod_name)

        # Helper for Inputs (Intercepts requests and resolves split buses)
        def res(bits): return resolve_bus(compiler, grid, bits, safe_mod_name, bit_registry)
    

        current_x = PIN_X_INIT
        current_y = PIN_Y_INIT

        ports = module_data.get("ports", {})
        for port_name, port_data in ports.items():
            bits = port_data.get("bits", [])
            is_input = (port_data.get("direction") == "input")
            
            wire = gw(bits) if is_input else res(bits)

            compiler.add_pin(x=current_x, y=current_y, wire=wire, pin_label=port_name, is_input=is_input)
            current_y += Y_SPACING

        current_x = X_INIT 
        current_y = Y_INIT


        cells = module_data.get("cells", {})

        for cell_name, cell_data in cells.items():
            c_type = cell_data["type"]
            conns = cell_data.get("connections", {})

            # This is the first time, but it might be reassigned multiple times
            x,y = grid.next() 

            # Original Name in Verilog
            clean_label = cell_name.lstrip('\\')
            # print("Original Label Name:", cell_name)

            if c_type == "cs_clock":
                out_wire = gw(conns.get("clk", []))
                compiler.add_clock(x=x, y=y, out_wire=out_wire)
                continue
            elif c_type == "cs_probe":
                in_wire = res(conns.get("val", []))
                compiler.add_pin(x=x, y=y, wire=in_wire, pin_label=clean_label, is_input=False)
                continue
            elif c_type == "cs_register":
                # Yosys will preserve exactly these ports: 'clk', 'clr', 'en', 'd', 'q'
                in_clk = res(conns.get("clk", []))
                in_clr = res(conns.get("clr", []))
                in_en  = res(conns.get("en", []))
                in_d   = res(conns.get("d", []))
                out_q  = gw(conns.get("q", []))

                compiler.add_register(
                    x=x, y=y,
                    in_d=in_d,
                    out_q=out_q,
                    in_clk=in_clk,
                    in_en=in_en,
                    in_clr=in_clr,
                    label=cell_name
                )
            
            # --- CUSTOM DYNAMIC BLACKBOX MULTIPLEXER ---
            elif c_type.startswith("cs_mux_"):
                match = re.search(r'cs_mux_(\d+)to1', c_type)
                if match:
                    num_inputs = int(match.group(1))
                    sel_bits = max(1, math.ceil(math.log2(num_inputs)))

                    out_wire = gw(conns.get("y", []))

                    # Dynamically fetch d0 through dN-1
                    in_wires = [res(conns.get(f"d{i}", [])) for i in range(num_inputs)]

                    compiler.add_mux(
                        x=x, y=y, sel_bits=sel_bits,
                        in_wires=in_wires,
                        in_sel=res(conns.get("sel", [])),
                        out=out_wire
                    )
                else:
                    print(f"\033[31m[!] Invalid Custom Mux format: {c_type}\033[0m")

            # --- FOLDED MULTIPLEXERS ---
            elif c_type == "$cs_folded_mux":
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                a_flat = conns.get("A", [])
                s_flat = conns.get("S", [])

                sel_bits = len(s_flat)
                num_inputs = 2 ** sel_bits

                in_wires = []
                for i in range(num_inputs):
                    # Slice the massive flat array back into distinct wire requests
                    chunk = a_flat[i * target_width : (i + 1) * target_width]
                    in_wires.append(res(chunk))

                compiler.add_mux(
                    x=x, y=y, sel_bits=sel_bits,
                    in_wires=in_wires,
                    in_sel=res(s_flat),
                    out=out_wire
                )

            elif not c_type.startswith("$") or c_type.startswith("$paramod$"):
                sub_name = c_type.split('\\')[-1].replace('$', '')

                # Fetch port definitions from the netlist to separate inputs from outputs
                sub_mod_data = netlist.get("modules", {}).get(c_type, {})
                sub_ports = sub_mod_data.get("ports", {})

                in_wires = []
                out_wires = []

                for p_name, p_data in sub_ports.items():
                    bits = conns.get(p_name, [])
                    if p_data.get("direction") == "input":
                        in_wires.append(res(bits))
                    elif p_data.get("direction") == "output":
                        out_wires.append(gw(bits))

                compiler.add_subcircuit(
                    x=x, y=y,
                    subcircuit_name=sub_name,
                    in_wires=in_wires,
                    out_wires=out_wires
                )

            elif c_type in ["$add", "$sub", "$mul"]:
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                ci_conn = conns.get("C", [])
                cin_wire = res(ci_conn if ci_conn else ['0']) 
                
                a_bits = res(conns.get("A", []))
                b_bits = res(conns.get("B", []))

                params = cell_data.get("parameters", {})
                a_signed = int(params.get("A_SIGNED", "0"), 2) == 1
                b_signed = int(params.get("B_SIGNED", "0"), 2) == 1

                a_wire = get_padded_wire(compiler, grid, a_bits, target_width, safe_mod_name, a_signed)
                b_wire = get_padded_wire(compiler, grid, b_bits, target_width, safe_mod_name, b_signed)

                if c_type == "$add":
                    peer = "AdderPeer"
                elif c_type == "$sub":
                    peer = "SubtractorPeer"
                elif c_type == "$mul":
                    peer = "MultiplierPeer"

                compiler.add_arithmetic(
                    peer_type=peer, x=x, y=y,
                    in_a=a_wire, in_b=b_wire, out=out_wire,
                    cin=cin_wire
                )

            # --- SHIFTERS ---
            elif c_type in ["$shl", "$shr", "$sshl", "$sshr"]:
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                a_raw = res(conns.get("A", []))
                b_raw = res(conns.get("B", []))

                params = cell_data.get("parameters", {})
                a_signed = int(params.get("A_SIGNED", "0"), 2) == 1
                b_signed = int(params.get("B_SIGNED", "0"), 2) == 1

                # CircuitSim shifter's 'B' input must exactly match ceil(log2(bitsize))
                b_target_width = max(1, math.ceil(math.log2(target_width)))

                a_wire = get_padded_wire(compiler, grid, a_raw, target_width, safe_mod_name, a_signed)

                # Handle B wire sizing strictly
                if b_raw.bitsize > b_target_width:
                    b_wire = Wire(f"W_SHF_TRUNC_{x}_{y}", b_target_width)
                    dummy_drop = Wire(None, b_raw.bitsize - b_target_width)
                    # Splitter truncates the upper bits and drops them into a dummy void
                    compiler.add_splitter(x, y, b_raw, [b_wire, dummy_drop])
                    x, y = grid.next() # Advance grid since we dropped a splitter hardware
                else:
                    b_wire = get_padded_wire(compiler, grid, b_raw, b_target_width, safe_mod_name, b_signed)

                # Determine Shift Type
                shift_type = "LOGICAL LEFT"
                if c_type in ["$shr", "$sshr"]:
                    if a_signed:
                        shift_type = "ARITHMETIC RIGHT"
                    else:
                        shift_type = "LOGICAL RIGHT"
                elif c_type == "$sshl":
                    shift_type = "LOGICAL LEFT"

                compiler.add_shifter(
                    x=x, y=y,
                    in_a=a_wire, in_b=b_wire, out=out_wire,
                    shift_type=shift_type
                )

                # --- LOGIC GATES ---
            elif c_type in ["$and", "$or", "$xor"]:
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                a_bits = res(conns.get("A", []))
                b_bits = res(conns.get("B", []))
                
                params = cell_data.get("parameters", {})
                a_signed = params.get("A_SIGNED", "0") == "1"
                b_signed = params.get("B_SIGNED", "0") == "1"

                a_wire = get_padded_wire(compiler, grid, a_bits, target_width, safe_mod_name, a_signed)
                b_wire = get_padded_wire(compiler, grid, b_bits, target_width, safe_mod_name, b_signed)

                gate = c_type.replace("$", "").capitalize()
                compiler.add_logic_gate(
                    gate_type=gate, x=x, y=y,
                    in_a=a_wire, in_b=b_wire, out=out_wire
                )

            elif c_type in ["$not"]:
                compiler.add_not_gate(
                    x=x, y=y,
                    in_a=res(conns.get("A", [])),
                    out=gw(conns.get("Y", []))
                )

            # --- NEGATOR (TWO'S COMPLEMENT) ---
            elif c_type == "$neg":
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                a_bits = res(conns.get("A", []))

                params = cell_data.get("parameters", {})
                a_signed = int(params.get("A_SIGNED", "0"), 2) == 1

                # Ensure the input is safely padded to the output width before negating
                a_wire = get_padded_wire(compiler, grid, a_bits, target_width, safe_mod_name, a_signed)

                compiler.add_negator(
                    x=x, y=y,
                    in_a=a_wire, out=out_wire
                )


                # --- COMPARATORS ---
            elif c_type in ("$eq", "$ne", "$gt", "$lt", "$ge", "$le", "$cs_mega_comparator"):
                a_raw = res(conns.get("A", [])) 
                b_raw = res(conns.get("B", []) )

                target_width = max(a_raw.bitsize, b_raw.bitsize)
                
                params = cell_data.get("parameters", {})
                a_signed = int(params.get("A_SIGNED", "0"), 2) == 1
                b_signed = int(params.get("B_SIGNED", "0"), 2) == 1
                
                a_wire = get_padded_wire(compiler, grid, a_raw, target_width, safe_mod_name, a_signed)
                b_wire = get_padded_wire(compiler, grid, b_raw, target_width, safe_mod_name, b_signed)

                # Figure out which output ports we actually need to wire up
                req_eq = conns.get("Y_EQ", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$eq" else [])
                req_ne = conns.get("Y_NE", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$ne" else [])
                req_lt = conns.get("Y_LT", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$lt" else [])
                req_ge = conns.get("Y_GE", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$ge" else [])
                req_gt = conns.get("Y_GT", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$gt" else [])
                req_le = conns.get("Y_LE", []) if c_type == "$cs_mega_comparator" else (conns.get("Y", []) if c_type == "$le" else [])

                # Map primary outputs directly to the comparator, or to temporary wires if we need to NOT them
                out_eq = gw(req_eq) if req_eq else (Wire(f"W_TMP_EQ_{x}_{y}", 1) if req_ne else None)
                out_lt = gw(req_lt) if req_lt else (Wire(f"W_TMP_LT_{x}_{y}", 1) if req_ge else None)
                out_gt = gw(req_gt) if req_gt else (Wire(f"W_TMP_GT_{x}_{y}", 1) if req_le else None)

                is_unsigned_comp = not (a_signed and b_signed)

                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire, in_b=b_wire,
                    out_eq=out_eq, out_greater=out_gt, out_less=out_lt,
                    is_unsigned=is_unsigned_comp
                )

                # Spawn NOT gates for the inverted comparisons if they were requested
                if req_ne:
                    x_n, y_n = grid.next()
                    compiler.add_not_gate(x_n, y_n, out_eq, gw(req_ne))
                if req_ge:
                    x_n, y_n = grid.next()
                    compiler.add_not_gate(x_n, y_n, out_lt, gw(req_ge))
                if req_le:
                    x_n, y_n = grid.next()
                    compiler.add_not_gate(x_n, y_n, out_gt, gw(req_le))

            elif c_type in ["$reduce_bool", "$reduce_or", "$reduce_and"]:
                a_wire = res(conns.get("A", []))
                zero_bus = res(['0'] * a_wire.bitsize)
                one_bus = res(['1'] * a_wire.bitsize)
                out_bus = gw(conns.get("Y", []))

                if c_type == "$reduce_and":
                    cmp_bus = one_bus 
                    out_eq = out_bus
                    out_gt = None
                else:
                    cmp_bus = zero_bus
                    out_eq = None
                    out_gt = out_bus

                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire,
                    in_b=cmp_bus,
                    out_eq=out_eq,
                    out_greater=out_gt,
                    is_unsigned=True
                )

            elif c_type == "$logic_not":
                a_wire = res(conns.get("A", []))
                y_wire = res(conns.get("Y", []))

                # Logical NOT: Is A exactly equal to 0?
                if a_wire.bitsize == 1:
                    compiler.add_not_gate(x=x, y=y, in_a=a_wire, out=y_wire)
                else:
                    zero_bus = res(['0'] * a_wire.bitsize)
                    compiler.add_comparator(
                        x=x, y=y,
                        in_a=a_wire,
                        in_b=zero_bus,
                        out_eq=y_wire
                    )

            elif c_type in ["$logic_and", "$logic_or"]:
                a_wire = res(conns.get("A", []))
                b_wire = res(conns.get("B", []))
                y_wire = gw(conns.get("Y", []))
                
                gate_type = "And" if c_type == "$logic_and" else "Or"

                if a_wire.bitsize == 1:
                    a_is_true = a_wire
                else:
                    a_is_true = Wire(f"L_{gate_type.upper()}_A_GT0_{x}_{y}", 1)

                    zero_bus = res(['0'] * a_wire.bitsize)

                    # 1. Compare A > 0 (Unsigned)
                    compiler.add_comparator(
                        x=x, y=y,
                        in_a=a_wire,
                        in_b=zero_bus,
                        out_greater=a_is_true,
                        is_unsigned=True
                    )

                    x, y = grid.next()

                if b_wire.bitsize == 1:
                    b_is_true = b_wire
                else:
                    b_is_true = Wire(f"L_{gate_type.upper()}_B_GT0_{x}_{y}", 1)
                    
                    zero_bus = res(['0'] * b_wire.bitsize)
                    
                    x, y = grid.next()
                    
                    # 2. Compare B > 0 (Unsigned)
                    compiler.add_comparator(
                        x=x, y=y,
                        in_a=b_wire,
                        in_b=zero_bus,
                        out_greater=b_is_true,
                        is_unsigned=True
                    )

                    x,y = grid.next()

                # 3. A is True AND B is True
                compiler.add_logic_gate(
                    gate_type=gate_type,
                    x=x, y=y,
                    in_a=a_is_true,
                    in_b=b_is_true,
                    out=y_wire
                )

                # --- MULTIPLEXERS ---
            elif c_type == "$mux":
                compiler.add_mux(
                    x=x, y=y, sel_bits=1,
                    in_wires=[res(conns.get("A", [])), res(conns.get("B", []))],
                    in_sel=res(conns.get("S", [])),
                    out=gw(conns.get("Y", []))
                )


            elif c_type == "$pmux":
                # --- NATIVE PMUX CONVERTER ---
                a_wire = res(conns.get("A", [])) # Fallback (Index 0)
                b_flat = conns.get("B", [])      # Flat array of data inputs
                s_flat = conns.get("S", [])      # 1-Hot selector array
                out_wire = gw(conns.get("Y", []))

                width = out_wire.bitsize
                s_width = len(s_flat)

                # 1. Determine Native CircuitSim Mux Size
                # We need s_width + 1 total cases (fallback + all 1-hot options)
                sel_bits = max(1, math.ceil(math.log2(s_width + 1)))
                num_mux_inputs = 2 ** sel_bits

                if sel_bits > 5:
                    print(f"\033[31m[!] WARNING: MUX requires {sel_bits} selector bits. CircuitSim may cap at 5 (32 inputs).\033[0m")

                # 2. Convert Flat Array into Discrete Indexed Wires
                in_wires = [a_wire] # Index 0 is always the Fallback
                for i in range(s_width):
                    # Slice the exact chunk of bits for this input
                    b_chunk = b_flat[i * width : (i + 1) * width]
                    in_wires.append(res(b_chunk))

                # CircuitSim Muxes must have exactly 2^N inputs. Pad the rest with Constant 0s.
                zero_pad = res(['0'] * width)
                while len(in_wires) < num_mux_inputs:
                    in_wires.append(zero_pad)

                # 3. The 1-Hot to Binary Priority Encoder
                sel_bit_wires = []
                for k in range(sel_bits):
                    # Find which 1-hot inputs require THIS binary bit to be '1'
                    active_s_wires = []
                    for i in range(s_width):
                        index = i + 1 # Offset by 1 because index 0 is the fallback

                        if (index & (1 << k)) != 0:
                            active_s_wires.append(res([s_flat[i]]))

                    # If no wires trigger this bit, tie it to 0
                    if not active_s_wires:
                        sel_bit_wires.append(res(['0']))
                    # If exactly 1 wire triggers it, route it directly (no gate needed!)
                    elif len(active_s_wires) == 1:
                        sel_bit_wires.append(active_s_wires[0])
                    # If multiple wires trigger it, spawn a Wide OR Gate
                    else:
                        x, y = grid.next()
                        k_out = Wire(f"PMUX_ENC_BIT_{k}_{x}_{y}", 1)
                        compiler.add_multi_logic_gate("Or", x, y, active_s_wires, k_out)
                        sel_bit_wires.append(k_out)

                # 4. Merge the 1-bit wires into the final Binary Selector Bus
                sel_bus = Wire(f"PMUX_SEL_BUS_{x}_{y}", sel_bits)
                x, y = grid.next()
                compiler.add_splitter(x, y, sel_bus, sel_bit_wires)

                # 5. Drop the Native Multiplexer
                x, y = grid.next()
                compiler.add_mux(
                    x=x, y=y, sel_bits=sel_bits,
                    in_wires=in_wires,
                    in_sel=sel_bus,
                    out=out_wire
                )


            # --- MEMORY & REGISTER FILES ---
            elif c_type in ["$mem", "$mem_v2"]:
                params = cell_data.get("parameters", {})
                addr_bits = int(params.get("ABITS", "0"), 2)
                width = int(params.get("WIDTH", "0"), 2)

                # Fetch the flattened connection arrays
                rd_addr_flat = conns.get("RD_ADDR", [])
                rd_data_flat = conns.get("RD_DATA", [])
                wr_en_array = conns.get("WR_EN", [])

                match clean_label:
                    case "IMEM":
                        final_label = "I-MEM"
                    case "DMEM":
                        final_label = "D-MEM"
                    case _:
                        final_label = clean_label

                is_rom = (not wr_en_array or all((b == '0' or b == 0) for b in wr_en_array)) and not final_label == "I-MEM"

                if is_rom:
                    # Yosys stores ROM contents in the INIT parameter as a massive string.
                    # We need to chunk it into integers.
                    init_str = params.get("INIT", "").zfill((2 ** addr_bits) * width)
                    contents_array = []

                    # Read the chunks (Note: Yosys INIT strings are usually LSB-first chunked, 
                                       # meaning the last chunk in the string is index 0. You may need to reverse this!)
                    for i in range(0, len(init_str), width):
                        chunk = init_str[i : i + width]
                        chunk = chunk.replace('x', '0').replace('z', '0')
                        contents_array.append(int(chunk, 2))

                    contents_array.reverse() # Usually required for Yosys INIT parsing

                    compiler.add_rom(
                        x=x, y=y,
                        addr_bits=addr_bits,
                        contents_array=contents_array,
                        in_addr=res(rd_addr_flat),
                        out_data=gw(rd_data_flat),
                        in_en=res(['1']) # Always enabled
                    )
                else:
                    wr_data_flat = conns.get("WR_DATA", [])
                    rd_en_array = conns.get("RD_EN", [])

                    str_wire = res([wr_en_array[0]] if wr_en_array else [])
                    ld_wire = res([rd_en_array[0]] if rd_en_array else ['1']) # Default LD to 1 if missing


                    # print("Writing Memory with label:", clean_label)

                    # Standard Single-Port RAM (Your standard Instruction/Data memory)
                    compiler.add_ram(
                        x=x, y=y,
                        addr_bits=addr_bits,
                        data_bits=width,
                        in_addr=res(rd_addr_flat), 
                        in_data=res(wr_data_flat),
                        out_data=gw(rd_data_flat),
                        in_clk=res(conns.get("WR_CLK", [])),
                        in_en=res(['1']), # Always Tie Enable to High
                        in_ld=ld_wire,
                        in_str=str_wire,
                        in_clr=res(['0']),  # Always Tie Reset to Low
                        label=final_label
                    )
            # --- REGISTERS (D-FLIP-FLOPS) ---
            elif c_type in ["$dff", "$dffe", "$sdff", "$sdffce", "$sdffe"]:
                out_wire = gw(conns.get("Q", []))
                in_wire = res(conns.get("D", []))
                clk_wire = res(conns.get("CLK", []))

                params = cell_data.get("parameters", {})

                # print(f"Starting {c_type} named {clean_label}")

                # 1. Check if we need an enable pin. Just default to High.
                en_conn = conns.get("EN", [])
                en_wire = res(en_conn) if en_conn else res(['1'])

                # And check if Yosys decided to make this Active-Low instead of the standard Active-High
                if en_conn and int(params.get("EN_POLARITY", "1"), 2) == 0:
                    inverted_en = Wire(f"W_INV_EN_{x}_{y}", 1)
                    x_not, y_not = grid.next()
                    compiler.add_not_gate(x=x_not, y=y_not, in_a=en_wire, out=inverted_en)
                    en_wire = inverted_en
                
                # 2. Reset Pin Setup
                # Synchronous Reset, which is an issue since our registers are Asynchronous
                rst_conn = conns.get("SRST", [])
                clr_wire = res(['0']) # Tie CLR to 0

                if rst_conn:
                    srst_wire = res(rst_conn)
                    # And also check if RST is Active-Low
                    if int(params.get("SRST_POLARITY", "1"), 2) == 0:
                        inverted_rst = Wire(f"W_INV_RST_{x}_{y}", 1)
                        x_not, y_not = grid.next()
                        compiler.add_not_gate(x=x_not, y=y_not, in_a=clr_wire, out=inverted_rst)
                        srst_wire = inverted_rst

                    # Basically, we fix this by putting the Actual Data and 0's into a MUX
                    # Then, we select whether to reset or not by tying the reset to the MUX
                    # Then, we use the ouput of the MUX into the Register
                    # And we also use the Enable Pin to put the data in
                    # We do not need to tie anything to the actual Register Reset Pin.

                    # Build a MUX to handle the Synchronous Reset
                    # Yosys outputs parameter values as string arrays (e.g. "00000000")
                    srst_val_bits = params.get("SRST_VALUE", "0" * in_wire.bitsize)
                    reset_const_wire = res(list(srst_val_bits))

                    mux_out_wire = Wire(f"W_SDFF_MUX_{x}_{y}", in_wire.bitsize)
                    x_m, y_m = grid.next()
                    compiler.add_mux(
                        x=x_m, y=y_m, sel_bits=1,
                        in_wires=[in_wire, reset_const_wire],
                        in_sel=srst_wire,
                        out=mux_out_wire
                    )

                    # The D-pin now safely receives the MUX output
                    in_wire = mux_out_wire

                    # If the DFF has an enable, a synchronous RST must force
                    # enable HIGH so that the register wakes up to capture the '0 from the MUX
                    if c_type == "$sdffe":
                        # We manually create a Wire here because we are building the source (the OR gate) right now
                        combined_en = Wire(f"W_SDFFE_EN_{x}_{y}", 1)

                        x_or, y_or = grid.next()
                        compiler.add_logic_gate(
                            gate_type="Or", x=x_or, y=y_or, 
                            in_a=en_wire, in_b=srst_wire, out=combined_en
                        )
                        # Overwrite the enable wire so the register uses our new OR gate output
                        en_wire = combined_en

                # 3. Resolve Custom Labels
                q_bits = tuple(conns.get("Q", []))
                final_label = reverse_netnames.get(q_bits, clean_label)
                # print(f"Found final label {final_label}")

            

                compiler.add_register(
                     x=x, y=y,
                     in_d=in_wire,
                     out_q=out_wire,
                     in_clk=clk_wire,
                     in_en=en_wire,
                     in_clr=clr_wire,
                     label=final_label
                )
            else:
                print(f"\033[31m[!] Unmapped component: {c_type}\033[0m")
                sys.exit(1)

    # ========================================================
    # FINAL STEP: Spawn all Constant values detected by Yosys
    # ========================================================
    num_constants = sum(len(sub) for sub in GLOBAL_CONSTANTS)
    print(f"[*] Spawning {num_constants} Hardcoded Constants...")

    for circ_name, constants_dict in GLOBAL_CONSTANTS.items():
        if circ_name not in compiler.circuits:
            print(f"[!] POTENTIAL ERROR: {circ_name} NOT IN CIRCUITS!")
            continue

        compiler.set_active_circuit(circ_name)
        const_x = 5
        const_y = 50
        for label, const_data in constants_dict.items():
            compiler.add_constant(
                x=const_x, y=const_y, 
                out=const_data["wire"], 
                value=const_data["val"] 
            )
            const_y += 30


if __name__ == "__main__":
    compiler = CircuitBuilder()

    OPTIMIZE = True 
    OPTIMIZE_TUNNELS = False
    # No cli flag yet...

    # 1. Parse the Silicon Netlist into the Compiler Memory
    parse_yosys_netlist(compiler, "build/netlist.json", OPTIMIZE)

    # 2. Optimize (Split) Tunnels
    if OPTIMIZE_TUNNELS:
        compiler.optimize_tunnel_clusters()

    # 3. Stats!
    compiler.print_stats()

    # 4. Forge the Signature and Save!
    compiler.save("build/cpu.sim", debug_labels=False)
