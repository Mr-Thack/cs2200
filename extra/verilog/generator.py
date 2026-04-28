import math
# Generates a 65536-entry hex file for the LC-5200b Superscalar Merge ROM

# --- ENUMS (Mapped directly to your SystemVerilog types) ---
# Opcodes
OP_ADD = 0x0; OP_NAND = 0x1; OP_ADDI = 0x2; OP_LW = 0x3; OP_SW = 0x4
OP_BEQ = 0x5; OP_JALR = 0x6; OP_HALT = 0x7; OP_BGT = 0x8; OP_LEA = 0x9

# Register Selectors
REG_IGNORE = 0; REG_RX = 1; REG_RY = 2; REG_RZ = 3; REG_INS2_RX = 4; REG_INS2_RY = 5

# ALU Sources
ALU_VAL1 = 0; ALU_VAL2 = 1; ALU_OFFSET = 2; ALU_PC = 3

# Operations
ALU_IGNORE = 0; ALU_ADD = 1; ALU_SUB = 2; ALU_NAND = 3; ALU_NEG = 4; ALU_PASSA = 5; ALU_PASSB = 6; ALU_ADD1 = 7
CMP_IGNORE = 0; CMP_LT = 1; CMP_EQ = 2; CMP_GT = 3
MEM_IGNORE = 0; MEM_READ = 1; MEM_WRITE = 2
LOGIC_IGNORE = 0; LOGIC_JMP_OFFSET = 1; LOGIC_JMP_RES = 2

class BitPacker:
    """Packs values dynamically from MSB to LSB, matching SV packed structs."""
    def __init__(self):
        self.value = 0
        self.total_bits = 0

    def add(self, val, bits):
        # Mask the value to ensure it doesn't bleed out of its allocated width
        val = val & ((1 << bits) - 1)
        # Shift the existing bits left to make room, then insert the new bits
        self.value = (self.value << bits) | val
        self.total_bits += bits
        return self # Allows chaining if you want

class BitUnpacker:
    """Unpacks a value sequentially from MSB to LSB."""
    def __init__(self, value, total_bits):
        self.value = value
        self.bits_left = total_bits

    def get(self, bits):
        if self.bits_left < bits:
            raise ValueError("Trying to unpack more bits than available!")
        self.bits_left -= bits
        # Shift right to bring the target bits to the bottom, then mask
        return (self.value >> self.bits_left) & ((1 << bits) - 1)


def write_verilog_hex(filename, data_list, bit_width):
    """
    Safely writes a list of integers to a hex file for Verilog $readmemh.
    Calculates the exact hex string length needed to prevent 'excess digits' errors.
    """
    # Calculate how many hex characters are needed (e.g., 28 bits / 4 = 7 chars)
    hex_chars = math.ceil(bit_width / 4)

    # Calculate the maximum allowed integer for this bit width
    max_val = (1 << bit_width) - 1

    with open(filename, "w") as f:
        for i, val in enumerate(data_list):
            if val > max_val:
                raise ValueError(f"CRITICAL: Control word at index {i} ({hex(val)}) exceeds {bit_width}-bit limit!")

            # Dynamically format the hex string to perfectly match the SV array width
            f.write(f"{val:0{hex_chars}x}\n")

    print(f"{filename} generated successfully with {bit_width}-bit formatting!")

def build_cw(instructions_merged=0, imm_sel=0, dr_sel=REG_IGNORE, sr1_sel=REG_IGNORE, 
             sr2_sel=REG_IGNORE, src1=ALU_VAL1, src2=ALU_VAL2, aluop=ALU_IGNORE, 
             cmpop=CMP_IGNORE, memop=MEM_IGNORE, logop=LOGIC_IGNORE, sig_halt=0):
    """Packs the control signals into a 28-bit integer."""
    # MAKE SURE TO MATCH THE CONTROL WORD TYPE IN TYPES.SV
    packer = BitPacker()

    # Read exactly top-to-bottom as defined in types.sv
    packer.add(dr_sel, 3)
    packer.add(sr1_sel, 3)
    packer.add(sr2_sel, 3)
    packer.add(imm_sel, 1)
    packer.add(src1, 2)
    packer.add(src2, 2)
    packer.add(aluop, 3)
    packer.add(cmpop, 3)
    packer.add(memop, 2)
    packer.add(logop, 3)
    packer.add(sig_halt, 1)
    packer.add(instructions_merged, 2)

    return packer.value

def generate_rom():
    rom_data = []

    # Iterate through all 65536 possible 16-bit addresses
    for addr in range(65536):
        unpacker = BitUnpacker(addr, total_bits=16)

        op1        = unpacker.get(4)
        op2        = unpacker.get(4)
        raw_dr_sr1 = unpacker.get(1)
        raw_dr_sr2 = unpacker.get(1)
        waw_dr_dr  = unpacker.get(1)
        is_sp      = unpacker.get(1)
        imm1_neg   = unpacker.get(1)
        imm1_pos   = unpacker.get(1)
        imm2_zero  = unpacker.get(1)
        imm2_one   = unpacker.get(1)

        cw = 0 # Default to 0 (Invalid fusion, fallback to single_rom)

        # -------------------------------------------------------------------
        # FUSION LOGIC RULES
        # -------------------------------------------------------------------

        # 1. TWO'S COMPLEMENT: NAND $reg, $reg, $reg + ADDI $reg, $reg, 1
        if op1 == OP_NAND and op2 == OP_ADDI and raw_dr_sr1 and waw_dr_dr and imm2_one:
            # Requires your ALU to treat ALU_ADD1 as ~A + 1
            cw = build_cw(
                instructions_merged=1, imm_sel=1, dr_sel=REG_RX, sr1_sel=REG_RY, sr2_sel=REG_RZ,
                src1=ALU_VAL1, src2=ALU_VAL2, aluop=ALU_NEG 
            )
        # 2. STACK PUSH: ADDI $sp, $sp, -x + SW $reg, 0($sp)
        # DISABLED BECAUSE I JUST REALIZED WE'RE WRITING TO 2 THINGS AT THE SAME TIME
        # CAUSING BAAAD BUGS
        if op1 == OP_ADDI and op2 == OP_SW and is_sp and raw_dr_sr1 and imm1_neg and imm2_zero:
            # We use ins1's immediate for the SP offset, and we need ins2's RX for the store data
            cw = build_cw(
                instructions_merged=1, imm_sel=0, dr_sel=REG_RX, sr1_sel=REG_INS2_RX, sr2_sel=REG_RY,
                src1=ALU_VAL2, src2=ALU_OFFSET, aluop=ALU_ADD, memop=MEM_WRITE
            )
        # 3. LEA + LW (Common in TwoSum.s for pointer dereferencing)
        # LEA $t0, label + LW $a0, 0($t0)
        elif op1 == OP_LEA and op2 == OP_LW and raw_dr_sr1 and imm2_zero:
            # Calculate LEA address (PC + ins1.imm), route to memory, write result to ins2.rx
            cw = build_cw(
                instructions_merged=1, imm_sel=0, dr_sel=REG_INS2_RX, sr1_sel=REG_IGNORE, 
                sr2_sel=REG_IGNORE, src1=ALU_PC, src2=ALU_OFFSET, aluop=ALU_ADD, memop=MEM_READ
            )

        rom_data.append(cw)


    # Write to a CircuitSim compatible format
    write_verilog_hex("merged_rom.hex", rom_data, bit_width=28)

if __name__ == "__main__":
    generate_rom()
