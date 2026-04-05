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


    def add_ram(self, x: int, y: int, addr_bits: int, in_addr: Wire, inout_data: Wire, 
                in_clk: Optional[Wire] = None, in_en: Optional[Wire] = None, 
                in_load: Optional[Wire] = None, in_clr: Optional[Wire] = None):
        """Standard RAM block (Single Port / Bidirectional Data)"""
        self._add_raw_component(
            "com.ra4king.circuitsim.gui.peers.memory.RAMPeer", x, y,
            {
                "Separate Load/Store Ports?": "No",
                "Label location": "NORTH",
                "Label": "",
                "Bitsize": str(inout_data.bitsize),
                "Address bits": str(addr_bits)
            }
        )
        self.add_tunnel(x - 7, y + 1, "EAST",  in_addr)
        self.add_tunnel(x + 9, y + 1, "WEST",  inout_data)

        self.add_tunnel(x,     y + 5, "NORTH", in_clk)
        self.add_tunnel(x + 1, y + 5, "NORTH", in_en)
        self.add_tunnel(x + 2, y + 5, "NORTH", in_load)
        self.add_tunnel(x + 3, y + 5, "NORTH", in_clr)

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
            self.add_tunnel(x - 7, y + i, "EAST", in_w)

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
            dy = 1
        elif bitsize <= 24:
            dy = 2
        else:
            dy = 3

        # X Offset: Output pins anchor on the right, so left-port dx is constant (-7).
        # Input pins/Constants anchor on the left, so right-port dx grows with text width.
        if is_output:
            dx = -7
        else:
            dx = 2 if bitsize == 1 else 8

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
        Passes over all components and replaces verbose wire labels 
        with guaranteed 6-character labels (e.g., T_0000, C_0000)
        """
        label_map = {}
        wire_counter = 0
        const_counter = 0

        for comp in self.components:
            props = comp.get("properties", {})

            # Tunnels and Pins use the "Label" property
            if "Label" in props and props["Label"]:
                old_label = props["Label"]

                # Check if it's one of our verbose deterministic labels
                if old_label.startswith("WIRE_") or old_label.startswith("CONST_") or old_label.startswith("PMUX_"):
                    if old_label not in label_map:
                        # Assign a new 6-character label
                        if old_label.startswith("CONST_"):
                            label_map[old_label] = f"C_{const_counter:04X}"
                            const_counter += 1
                        else:
                            label_map[old_label] = f"T_{wire_counter:04X}"
                            wire_counter += 1

                    # Overwrite the property directly in the JSON dictionary
                    props["Label"] = label_map[old_label]

    def save(self, filename: str):
        self._remap_labels()

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
# TRANSLATION / COMPILATION LAYER 
# ==========================================

# Global tracker for constants so we can spawn them at the end
GLOBAL_CONSTANTS = {}

def get_wire(bits_array) -> Wire:
    """
    Generates a properly sized Wire with a verbose, deterministic label.
    These will be remapped to 6 characters right before saving.
    """
    bitsize = len(bits_array)
    if bitsize == 0:
        return Wire(None, 0)

    # Check if this is a constant array (strings of '0', '1', 'x')
    if isinstance(bits_array[0], str):
        val_str = "".join(str(b) for b in reversed(bits_array)).replace('x', '0')
        val_hex = f"{int(val_str, 2):X}"

        # Verbose, deterministic constant label
        label = f"CONST_VAL_{val_hex}_BITS_{bitsize}"
        wire = Wire(label, bitsize)

        GLOBAL_CONSTANTS[label] = {"wire": wire, "val": val_hex}
        return wire

    # Find the first actual wire ID to name the bus
    first_id = next((b for b in bits_array if isinstance(b, int)), None)
    if first_id is not None:
        return Wire(f"WIRE_ID_{first_id}", bitsize)

    return Wire(None, 0)


def parse_yosys_netlist(compiler: CircuitBuilder, json_file_path: str):
    """
    The main compilation loop.
    """
    with open(json_file_path, 'r') as f:
        netlist = json.load(f)

    current_x = 50
    current_y = 50
    Y_SPACING = 80 

    for module_name, module_data in netlist.get("modules", {}).items():
        print(f"[*] Compiling module: {module_name}")
        cells = module_data.get("cells", {})

        for cell_name, cell_data in cells.items():
            c_type = cell_data["type"]
            conns = cell_data.get("connections", {})

            # --- ARITHMETIC ---
            if c_type in ["$add", "$sub"]:
                peer = "AdderPeer" if c_type == "$add" else "SubtractorPeer"
                compiler.add_arithmetic(
                    peer_type=peer, x=current_x, y=current_y,
                    in_a=get_wire(conns.get("A", [])),
                    in_b=get_wire(conns.get("B", [])),
                    out=get_wire(conns.get("Y", []))
                )

                # --- LOGIC GATES ---
            elif c_type in ["$logic_and", "$and", "$logic_or", "$or", "$logic_xor", "$xor"]:
                gate = c_type.replace("$", "").replace("logic_", "").capitalize()
                compiler.add_logic_gate(
                    gate_type=gate, x=current_x, y=current_y,
                    in_a=get_wire(conns.get("A", [])),
                    in_b=get_wire(conns.get("B", [])),
                    out=get_wire(conns.get("Y", []))
                )

            elif c_type in ["$logic_not", "$not"]:
                compiler.add_not_gate(
                    x=current_x, y=current_y,
                    in_a=get_wire(conns.get("A", [])),
                    out=get_wire(conns.get("Y", []))
                )

                # --- COMPARATORS ---
            elif c_type == "$eq":
                compiler.add_comparator(
                    x=current_x, y=current_y,
                    in_a=get_wire(conns.get("A", [])),
                    in_b=get_wire(conns.get("B", [])),
                    out_eq=get_wire(conns.get("Y", []))
                )

            elif c_type == "$reduce_bool":
                a_wire = get_wire(conns.get("A", []))
                compiler.add_comparator(
                    x=current_x, y=current_y,
                    in_a=a_wire,
                    in_b=Wire(f"C_0_{a_wire.bitsize}", a_wire.bitsize), # Compare to 0
                    out_greater=get_wire(conns.get("Y", []))
                )
                GLOBAL_CONSTANTS[f"C_0_{a_wire.bitsize}"] = {
                    "wire": Wire(f"C_0_{a_wire.bitsize}", a_wire.bitsize), "val": "0"
                }

                # --- MULTIPLEXERS ---
            elif c_type == "$mux":
                compiler.add_mux(
                    x=current_x, y=current_y, sel_bits=1,
                    in_wires=[get_wire(conns.get("A", [])), get_wire(conns.get("B", []))],
                    in_sel=get_wire(conns.get("S", [])),
                    out=get_wire(conns.get("Y", []))
                )

            elif c_type == "$pmux":
                # ONE-HOT CASCADING RESOLVER
                a_wire = get_wire(conns.get("A", []))
                b_flat = conns.get("B", [])
                s_flat = conns.get("S", [])
                out_wire = get_wire(conns.get("Y", []))
                width = out_wire.bitsize

                current_fallback = a_wire
                for i in range(len(s_flat)):
                    # Chunk out the target B bus and S bit
                    b_chunk = b_flat[i*width : (i+1)*width]
                    s_chunk = [s_flat[i]]

                    b_wire = get_wire(b_chunk)
                    s_wire = get_wire(s_chunk)

                    is_last = (i == len(s_flat) - 1)
                    # Temporary wire connecting this MUX to the next one
                    mux_out = out_wire if is_last else Wire(f"PMUX_TEMP_{i}_{current_x}_{current_y}", width)

                    compiler.add_mux(
                            x=current_x, y=current_y, sel_bits=1,
                            in_wires=[current_fallback, b_wire],
                            in_sel=s_wire,
                            out=mux_out
                            )
                    current_fallback = mux_out
                    current_y += Y_SPACING

                # --- MEMORY ---
            elif c_type in ["$mem", "$mem_v2"]:
                mem_id = cell_data.get("parameters", {}).get("MEMID", "")
                print(f"[*] Memory Block {mem_id} mapping triggered.")

                # Defaulting to standard RAM logic
                we_wire_array = conns.get("WR_EN", [])
                we_wire = get_wire([we_wire_array[0]] if we_wire_array else [])

                compiler.add_ram(
                    x=current_x, y=current_y,
                    addr_bits=len(conns.get("RD_ADDR", [])),
                    in_addr=get_wire(conns.get("RD_ADDR", [])),
                    inout_data=get_wire(conns.get("RD_DATA", [])), 
                    in_clk=get_wire(conns.get("RD_CLK", [])),
                    in_en=get_wire(conns.get("RD_EN", [])),
                    in_load=we_wire
                )

            else:
                print(f"[!] Unmapped component: {c_type}")

            current_y += Y_SPACING
            if current_y > 2000:
                current_y = 50
                current_x += 150

    # ========================================================
    # FINAL STEP: Spawn all Constant values detected by Yosys
    # ========================================================
    print(f"[*] Spawning {len(GLOBAL_CONSTANTS)} Hardcoded Constants...")
    const_x = 10
    const_y = 50
    for label, const_data in GLOBAL_CONSTANTS.items():
        compiler.add_constant(
            x=const_x, y=const_y, 
            out=const_data["wire"], 
            value=const_data["val"] 
        )
        const_y += 40
        if const_y > 2000:
            const_y = 50
            const_x += 80



if __name__ == "__main__":
    compiler = CircuitBuilder()

    # 1. Parse the Silicon Netlist into the Compiler Memory
    parse_yosys_netlist(compiler, "netlist.json")

    # 2. Forge the Signature and Save!
    compiler.save("cpu.sim")
