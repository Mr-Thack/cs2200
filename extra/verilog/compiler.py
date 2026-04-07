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
                in_en: Wire, in_ld: Wire, in_str: Wire, in_clr: Wire):
        """Standard RAM block (Separate Load/Store Ports Active)"""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.RAMPeer", x, y,
            {
                "Separate Load/Store Ports?": "Yes",
                "Label location": "NORTH",
                "Label": "",
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
        self.add_tunnel(x - 7, y + 1, "EAST",  in_addr)
        self.add_tunnel(x + 9, y + 1, "WEST",  out_data)
        self.add_tunnel(x + 1, y + 5, "NORTH", in_en)

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
        self.add_tunnel(x - 6, y, "EAST", a)
        self.add_tunnel(x - 2, y + 2, "NORTH", en)
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
        # Left
        self.add_tunnel(x - 6, y + 1, "EAST",  in_d)
        self.add_tunnel(x - 6, y + 2, "EAST",  in_en)

        # Right (Output)
        self.add_tunnel(x + 4, y + 1, "WEST",  out_q)

        # Bottom (CLK & CLR)
        self.add_tunnel(x - 2, y + 4, "NORTH", in_clk)
        self.add_tunnel(x    , y + 4, "NORTH", in_clr)

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
        # Y Offset: connection port shifts down as lines wrap
        if bitsize <= 8:
            dy = 0
        elif bitsize <= 16:
            dy = 0
        elif bitsize <= 24:
            dy = 1
        else:
            dy = 2

        # X Offset: Output pins anchor on the right, so left-port dx is constant (-7).
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

            if is_output:
                dx -= offset
            else:
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

        if is_input:
            self.add_tunnel(x + dx, y + dy, "WEST", wire)
        else:
            self.add_tunnel(x + dx, y + dy, "EAST", wire)

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
                    if old_label.startswith(("W_", "CONST_", "PMUX_", "L_AND_")):
                        if old_label not in label_map:
                            if old_label.startswith("CONST_"):
                                label_map[old_label] = f"C_{const_counter:04X}"
                                const_counter += 1
                            else:
                                label_map[old_label] = f"T_{wire_counter:04X}"
                                wire_counter += 1

                        props["Label"] = label_map[old_label]

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

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=2)

        total_components = sum(len(c["components"]) for c in self.circuits.values())
        print(f"[*] Success: Compiled {total_components} components across {len(self.circuits)} circuits to {filename}")


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
        if c_type in ["$add", "$sub", "$and", "$or", "$xor", "$not", "$eq", "$gt", "$lt", 
                      "$mux", "$pmux", "$logic_not", "$logic_and", "$logic_or", 
                      "$reduce_or", "$reduce_bool"]:
            output_ports = ["Y"]
        elif c_type in ["$mem", "$mem_v2"]:
            output_ports = ["RD_DATA"]
        elif c_type == "$dff":
            output_ports = ["Q"]
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
        wire = Wire(label, bitsize)

        if safe_module_name not in GLOBAL_CONSTANTS:
            GLOBAL_CONSTANTS[safe_module_name] = {}

        GLOBAL_CONSTANTS[safe_module_name][label] = {"wire": wire, "val": val_str}
        return wire

    # Create a unique string out of the exact bit array and module scope
    # e.g., "mem_5_6_7_8"
    bit_str = "_".join(str(b) for b in bits_array)
    unique_id = f"W_{safe_module_name}_{bit_str}"

    return Wire(unique_id, bitsize)

def resolve_bus(compiler: CircuitBuilder, grid, raw_bits: List[int], current_module: str, bit_registry: dict) -> Wire:
    """
    Intercepts an input bus request. Physically synthesizes Splitters/Mergers
    on the grid if the bus is fractured (sliced or mixed with constants).
    """
    if not raw_bits:
        return Wire(None, 0)

    # 1. Pure Constant Check (Handled by your existing logic)
    if all(isinstance(b, str) for b in raw_bits):
        return get_wire(raw_bits, current_module)

    # 2. Segment the requested bus into strictly contiguous chunks
    chunks = []
    current_chunk = []
    current_parent = None

    for b in raw_bits:
        parent = bit_registry.get(b, "CONSTANT") if isinstance(b, int) else "CONSTANT"

        is_contiguous = False
        if parent != "CONSTANT" and current_parent == parent and current_chunk:
            # Check if this bit is perfectly adjacent to the previous bit in the parent array
            prev_idx = parent.index(current_chunk[-1])
            curr_idx = parent.index(b)
            if curr_idx == prev_idx + 1:
                is_contiguous = True

        if parent == current_parent and (parent == "CONSTANT" or is_contiguous):
            current_chunk.append(b)
        else:
            if current_chunk:
                chunks.append((current_parent, current_chunk))
            current_chunk = [b]
            current_parent = parent

    if current_chunk:
        chunks.append((current_parent, current_chunk))

    # 3. Pure Parent Check: No hardware needed!
    if len(chunks) == 1:
        parent, chunk = chunks[0]
        if parent == tuple(raw_bits):
            return get_wire(raw_bits, current_module)

    # 4. Synthesize Physical Hardware for Fractured Buses
    chunk_wires = []
    for parent, chunk in chunks:
        if parent == "CONSTANT":
            chunk_wires.append(get_wire(chunk, current_module))
        elif len(chunk) == len(parent):
            chunk_wires.append(get_wire(list(parent), current_module))
        else:
            # Sliced Bus: We must physically tap the Parent Bus
            start_idx = parent.index(chunk[0])
            end_idx = start_idx + len(chunk)

            out_wires = []
            if start_idx > 0:
                out_wires.append(Wire(None, start_idx)) # Pre-chunk dummy drop

            tap_wire = Wire(f"W_TAP_{chunk[0]}_to_{chunk[-1]}_{grid.x}_{grid.y}", len(chunk))
            out_wires.append(tap_wire)

            if end_idx < len(parent):
                out_wires.append(Wire(None, len(parent) - end_idx)) # Post-chunk dummy drop

            x, y = grid.next()
            compiler.add_splitter(x, y, get_wire(list(parent), current_module), out_wires)
            chunk_wires.append(tap_wire)

    # 5. Merge Multiple Chunks together
    if len(chunk_wires) > 1:
        merged_label = "_".join(str(b) for b in raw_bits[:3]) # Shorten name to avoid massive strings
        target_wire = Wire(f"W_MERGE_{merged_label}_{grid.x}_{grid.y}", len(raw_bits))

        x, y = grid.next()
        # The Splitter is bidirectional. Connecting target to in_bus and chunks to out_wires merges them.
        compiler.add_splitter(x, y, target_wire, chunk_wires)
        return target_wire

    return chunk_wires[0]


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
                    target_width: int, is_signed: bool = False) -> Wire:
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

    
    x, y = grid.next()

    # Instruct the compiler to build the physical bridging component
    compiler.add_bit_extender(x, y, original_wire, padded_wire, is_signed)

    # print(f"Adding Padding for {original_wire.label} to {padded_wire.label}")

    return padded_wire



def parse_yosys_netlist(compiler: CircuitBuilder, json_file_path: str):
    """
    The main compilation loop.
    """
    with open(json_file_path, 'r') as f:
        netlist = json.load(f)

    X_SPACING = 25 
    Y_SPACING = 25 
    X_INIT = 50
    Y_INIT = 50
    
    PIN_X_INIT = 25
    PIN_Y_INIT = 25

    X_MAX = 100

    for module_name, module_data in netlist.get("modules", {}).items():
        safe_mod_name = module_name.split('\\')[-1].replace('$', '')

        # Determine if this is the top level module (Fallback to Main)
        if module_data.get("attributes", {}).get("top", 0) == 1:
            safe_mod_name = "Main"

        print(f"[*] Compiling module: {module_name}")

        bit_registry = build_bit_registry(module_data, netlist)

        compiler.set_active_circuit(safe_mod_name)

        # Helper for Outputs (Directly defines parent buses)
        def gw(bits): return get_wire(bits, safe_mod_name)

        # Helper for Inputs (Intercepts requests and resolves split buses)
        def res(bits): return resolve_bus(compiler, grid, bits, safe_mod_name, bit_registry)
    

        current_x = PIN_X_INIT
        current_y = PIN_Y_INIT

        ports = module_data.get("ports", {})
        for port_name, port_data in ports.items():
            is_input = (port_data.get("direction") == "input")
            wire = gw(port_data.get("bits", []))
            compiler.add_pin(x=current_x, y=current_y, wire=wire, pin_label=port_name, is_input=is_input)
            current_y += Y_SPACING

        current_x = X_INIT 
        current_y = Y_INIT

        grid = GridAllocator(X_INIT, Y_INIT, X_SPACING, Y_SPACING, X_MAX)
        
        cells = module_data.get("cells", {})

        for cell_name, cell_data in cells.items():
            c_type = cell_data["type"]
            conns = cell_data.get("connections", {})

            # This is the first time, but it might be reassigned multiple times
            x,y = grid.next() 

            # --- ARITHMETIC ---
            if not c_type.startswith("$") or c_type.startswith("$paramod$"):
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

            elif c_type in ["$add", "$sub"]:
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                ci_conn = conns.get("C", [])
                cin_wire = res(ci_conn if ci_conn else ['0']) 
                
                a_bits = res(conns.get("A", []))
                b_bits = res(conns.get("B", []))

                a_wire = get_padded_wire(compiler, grid, a_bits, target_width)
                b_wire = get_padded_wire(compiler, grid, b_bits, target_width)

                peer = "AdderPeer" if c_type == "$add" else "SubtractorPeer"
                compiler.add_arithmetic(
                    peer_type=peer, x=x, y=y,
                    in_a=a_wire, in_b=b_wire, out=out_wire,
                    cin=cin_wire
                )

                # --- LOGIC GATES ---
            elif c_type in ["$and", "$or", "$xor"]:
                out_wire = gw(conns.get("Y", []))
                target_width = out_wire.bitsize

                a_bits = res(conns.get("A", []))
                b_bits = res(conns.get("B", []))

                a_wire = get_padded_wire(compiler, grid, a_bits, target_width)
                b_wire = get_padded_wire(compiler, grid, b_bits, target_width)

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

                # --- COMPARATORS ---
            elif c_type in ("$eq", "$gt", "$lt"):
                out_wire = gw(conns.get("Y", []))

                a_raw = res(conns.get("A", [])) 
                b_raw = res(conns.get("B", []) )

                target_width = max(a_raw.bitsize, b_raw.bitsize)
                
                a_wire = get_padded_wire(compiler, grid, a_raw, target_width)
                b_wire = get_padded_wire(compiler, grid, b_raw, target_width)

                out_eq = out_wire if c_type == "$eq" else None
                out_gt = out_wire if c_type == "$gt" else None
                out_lt = out_wire if c_type == "$lt" else None

                params = cell_data.get("parameters", {})
                is_signed = params.get("A_SIGNED", "0") == "1"

                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire, in_b=b_wire,
                    out_eq=out_eq, out_greater=out_gt, out_less=out_lt,
                    is_unsigned=not is_signed
                )

            elif c_type in ["$reduce_bool", "$reduce_or"]:
                a_wire = res(conns.get("A", []))
                zero_bus = res(['0'] * a_wire.bitsize)
                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire,
                    in_b=zero_bus, # Compare to 0
                    out_greater=gw(conns.get("Y", [])),
                    is_unsigned=True
                )

            elif c_type == "$logic_not":
                a_wire = res(conns.get("A", []))
                zero_bus = res(['0'] * a_wire.bitsize)

                # Logical NOT: Is A exactly equal to 0?
                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire,
                    in_b=zero_bus,
                    out_eq=gw(conns.get("Y", []))
                )

            elif c_type in ["$logic_and", "$logic_or"]:
                a_wire = res(conns.get("A", []))
                b_wire = res(conns.get("B", []))
                y_wire = gw(conns.get("Y", []))
                
                gate_type = "And" if c_type == "$logic_and" else "Or"

                # Intermediate wires
                a_is_true = Wire(f"L_{gate_type.upper()}_A_GT0_{x}_{y}", 1)
                b_is_true = Wire(f"L_{gate_type.upper()}_B_GT0_{x}_{y}", 1)

                zero_bus = res(['0'] * a_wire.bitsize)

                # 1. Compare A > 0 (Unsigned)
                compiler.add_comparator(
                    x=x, y=y,
                    in_a=a_wire,
                    in_b=zero_bus,
                    out_greater=a_is_true,
                    is_unsigned=True
                )

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
                    x=x, y=y - (Y_SPACING // 2),
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
                # ONE-HOT CASCADING RESOLVER
                a_wire = res(conns.get("A", []))
                b_flat = conns.get("B", [])
                s_flat = conns.get("S", [])
                out_wire = gw(conns.get("Y", []))
                width = out_wire.bitsize

                current_fallback = a_wire
                for i in range(len(s_flat)):
                    # Chunk out the target B bus and S bit
                    b_chunk = b_flat[i*width : (i+1)*width]
                    s_chunk = [s_flat[i]]

                    b_wire = res(b_chunk)
                    s_wire = res(s_chunk)

                    is_last = (i == len(s_flat) - 1)
                    # Temporary wire connecting this MUX to the next one
                    mux_out = out_wire if is_last else Wire(f"PMUX_TEMP_{i}_{x}_{y}", width)

                    compiler.add_mux(
                        x=x, y=y, sel_bits=1,
                        in_wires=[current_fallback, b_wire],
                        in_sel=s_wire,
                        out=mux_out
                    )
                    current_fallback = mux_out

                    if i < len(s_flat) - 1:
                        # Not last iteration
                        x, y = grid.next()

            # --- MEMORY & REGISTER FILES ---
            elif c_type in ["$mem", "$mem_v2"]:
                params = cell_data.get("parameters", {})
                addr_bits = int(params.get("ABITS", "0"), 2)
                width = int(params.get("WIDTH", "0"), 2)

                # Fetch the flattened connection arrays
                rd_addr_flat = conns.get("RD_ADDR", [])
                rd_data_flat = conns.get("RD_DATA", [])
                wr_data_flat = conns.get("WR_DATA", [])

                # Extract the 1-bit Write Enable signal from the array
                wr_en_array = conns.get("WR_EN", [])
                rd_en_array = conns.get("RD_EN", [])


                str_wire = res([wr_en_array[0]] if wr_en_array else [])
                ld_wire = res([rd_en_array[0]] if rd_en_array else ['1']) # Default LD to 1 if missing

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
                    in_clr=res(['0'])  # Always Tie Reset to Low
                )
            # --- REGISTERS (D-FLIP-FLOPS) ---
            elif c_type == "$dff":
                compiler.add_register(
                     x=x, y=y,
                     in_d=res(conns.get("D", [])),
                     out_q=gw(conns.get("Q", [])),
                     in_clk=res(conns.get("CLK", [])),
                     in_en=res(['1']),  # CircuitSim needs Enable HIGH to write
                     in_clr=res(['0'])  # CircuitSim needs Clear LOW to avoid wiping memory
                )
            else:
                print(f"[!] Unmapped component: {c_type}")

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

    # 1. Parse the Silicon Netlist into the Compiler Memory
    parse_yosys_netlist(compiler, "build/netlist.json")

    # 2. Forge the Signature and Save!
    compiler.save("build/cpu.sim", debug_labels=True)
