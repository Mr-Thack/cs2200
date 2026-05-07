import math
from z3 import *
import json
import os
from multiprocessing import Pool, Manager, cpu_count


# =============================================================================
# SETTINGS 
# =============================================================================
NUM_CORES = 4  # Because we have 4 cores on our CPU 
# WHEN SCALING WORD_SIZE AND MEM_SIZE AND IMM_SIZE, KEEP THEM PROPORTIONAL
# AND BE CAREFUL WITH OVERFLOW'S

# WORD_SIZE = 32
# IMM_SIZE = 20
# ADDR_SIZE = 16

# WORD_SIZE = 16
# IMM_SIZE = 10
# ADDR_SIZE = 8

WORD_SIZE = 8
IMM_SIZE = 5
ADDR_SIZE = 4

# =============================================================================
# HELPERS 
# =============================================================================

# Opcodes
OP_ADD = 0; OP_NAND = 1; OP_ADDI = 2; OP_LW = 3; OP_SW = 4
OP_BEQ = 5; OP_JALR = 6; OP_HALT = 7; OP_BGT = 8; OP_LEA = 9

# ALU Ops & Sources
ALU_IGNORE = 0; ALU_ADD = 1; ALU_SUB = 2; ALU_NAND = 3
ALU_NEG = 4; ALU_PASSA = 5; ALU_PASSB = 6; ALU_ADD1 = 7
ALU_VAL1 = 0; ALU_VAL2 = 1; ALU_OFFSET = 2; ALU_PC = 3

# Mem & Cmp Ops
MEM_IGNORE = 0; MEM_READ = 1; MEM_WRITE = 2
CMP_IGNORE = 0; CMP_LT = 1; CMP_EQ = 2; CMP_GT = 3
LOGIC_IGNORE = 0; LOGIC_JMP_OFFSET = 1; LOGIC_JMP_RES = 2

# Selectors
REG_IGNORE = 0; REG_RX = 1; REG_RY = 2; REG_RZ = 3
REG_INS2_RX = 4; REG_INS2_RY = 5; REG_INS2_RZ = 6; REG_PC = 7

AGU_IGNORE = 0; AGU_READ1 = 1; AGU_READ2 = 2; AGU_PC = 3

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

def build_cw(dr_sel=REG_IGNORE, sr1_sel=REG_IGNORE, sr2_sel=REG_IGNORE,
             use_agu=0, agu_base_sel=AGU_IGNORE, agu_index_sel=AGU_IGNORE, agu_offset_sel=0,
             imm_sel=0, src1=ALU_VAL1, src2=ALU_VAL2, mem_write_source=0,
             aluop=ALU_IGNORE, cmpop=CMP_IGNORE, memop=MEM_IGNORE, logop=LOGIC_IGNORE,
             sig_halt=0):
    """Packs the control signals into a 32-bit integer."""
    # MAKE SURE TO MATCH THE CONTROL WORD TYPE IN TYPES.SV
    packer = BitPacker()

    # Read exactly top-to-bottom as defined in types.sv
    packer.add(dr_sel, 3)

    packer.add(sr1_sel, 3)
    packer.add(sr2_sel, 3)

    packer.add(use_agu, 1)
    packer.add(agu_base_sel, 2)
    packer.add(agu_index_sel, 2)
    packer.add(agu_offset_sel, 1)

    packer.add(imm_sel, 1)

    packer.add(src1, 2)
    packer.add(src2, 2)

    packer.add(mem_write_source, 1)

    packer.add(aluop, 3)
    packer.add(cmpop, 2)
    packer.add(memop, 2)
    packer.add(logop, 2)

    packer.add(sig_halt, 1)

    return packer.value

OP_NAMES = {0: "ADD", 1: "NAND", 2: "ADDI", 3: "LW", 4: "SW", 5: "BEQ", 6: "JALR", 7: "HALT", 8: "BGT", 9: "LEA"}

def compress_flags(terms):
    """
    Takes a list of binary strings like '00101111' and merges them into 'XX101111' 
    when the difference is irrelevant
    """
    if not terms: return []
    terms = set(terms)
    merged = True
    while merged:
        merged = False
        new_terms = set()
        marked = set()
        term_list = list(terms)
        for i in range(len(term_list)):
            for j in range(i+1, len(term_list)):
                t1, t2 = term_list[i], term_list[j]

                # Check how many bits differ between the two strings
                diffs = sum(1 for a, b in zip(t1, t2) if a != b)
                if diffs == 1:
                    # Find the differing index and replace with 'X'
                    idx = next(k for k in range(len(t1)) if t1[k] != t2[k])
                    new_term = t1[:idx] + 'X' + t1[idx+1:]
                    new_terms.add(new_term)
                    marked.add(t1)
                    marked.add(t2)
                    merged = True

        # Keep terms that couldn't be merged further
        new_terms.update(terms - marked)
        terms = new_terms
    return sorted(list(terms))

# =============================================================================
# STATE
# =============================================================================

class CPUState:
    def __init__(self, read_reg_func, mem_w_en, mem_w_addr, mem_w_data, mem_r_en, mem_r_addr, mem_count):
        self.read_reg = read_reg_func
        self.mem_write_en = mem_w_en
        self.mem_write_addr = mem_w_addr
        self.mem_write_data = mem_w_data
        self.mem_read_en = mem_r_en
        self.mem_read_addr = mem_r_addr
        self.mem_count = mem_count

    def with_reg_write(self, w_en, w_reg, w_val):
        # Creates a new lookup function: if reading the written register, return the new value. 
        # Otherwise, fall back to the old lookup function (data forwarding!)
        def next_read(reg_id):
            return If(And(w_en, w_reg != 0, reg_id == w_reg), w_val, self.read_reg(reg_id))
        return CPUState(next_read, self.mem_write_en, self.mem_write_addr, self.mem_write_data, self.mem_read_en, self.mem_read_addr, self.mem_count)

    def with_mem_write(self, w_en, w_addr, w_data):
        next_en = Or(self.mem_write_en, w_en)
        next_addr = If(w_en, w_addr, self.mem_write_addr)
        next_data = If(w_en, w_data, self.mem_write_data)
        next_count = self.mem_count + If(w_en, BitVecVal(1, 4), BitVecVal(0, 4))
        return CPUState(self.read_reg, next_en, next_addr, next_data, self.mem_read_en, self.mem_read_addr, next_count)

    def with_mem_read(self, r_en, r_addr):
        next_en = Or(self.mem_read_en, r_en)
        next_addr = If(r_en, r_addr, self.mem_read_addr)
        next_count = self.mem_count + If(r_en, BitVecVal(1, 4), BitVecVal(0, 4))
        return CPUState(self.read_reg, self.mem_write_en, self.mem_write_addr, self.mem_write_data, next_en, next_addr, next_count)


def execute_sequential_symbolic(opcode, rx, ry, rz, imm, pc, mem_read_val, state):
    imm_ext = SignExt(WORD_SIZE - IMM_SIZE, imm)

    val1 = state.read_reg(ry)
    val2 = state.read_reg(rz)

    addr32 = val1 + imm_ext

    # Precompute possible results
    res_add = val1 + val2
    res_nand = ~(val1 & val2)
    res_addi = val1 + imm_ext
    res_lw = mem_read_val
    res_lea = pc + 1 + imm_ext

    writes_reg = Or(opcode == OP_ADD, opcode == OP_NAND, opcode == OP_ADDI, opcode == OP_LW, opcode == OP_LEA)
    write_val = If(opcode == OP_ADD, res_add,
                If(opcode == OP_NAND, res_nand,
                If(opcode == OP_ADDI, res_addi,
                If(opcode == OP_LW, res_lw,
                If(opcode == OP_LEA, res_lea, BitVecVal(0, WORD_SIZE))))))

    # Calculate updates
    next_state = state.with_reg_write(writes_reg, rx, write_val)
    next_state = next_state.with_mem_write(opcode == OP_SW, addr32, state.read_reg(rx))
    next_state = next_state.with_mem_read(opcode == OP_LW, addr32)

    return next_state

# =============================================================================
# DATAPATH MODEL
# =============================================================================

def execute_fused(ins1, ins2, cw, pc, mem_read_val, state):
    imm1_ext = SignExt(WORD_SIZE - IMM_SIZE, ins1['imm'])
    imm2_ext = SignExt(WORD_SIZE - IMM_SIZE, ins2['imm'])
    pc_plus_1 = pc + 1

    def mux_reg_sel(sel):
        return If(sel == REG_RX, ins1['rx'],
               If(sel == REG_RY, ins1['ry'],
               If(sel == REG_RZ, ins1['rz'],
               If(sel == REG_INS2_RX, ins2['rx'],
               If(sel == REG_INS2_RY, ins2['ry'],
               If(sel == REG_INS2_RZ, ins2['rz'], 
               BitVecVal(0, 4)))))))

    # --- DECODE STAGE ---
    dr  = mux_reg_sel(cw['dr_sel'])
    sr1 = mux_reg_sel(cw['sr1_sel'])
    sr2 = mux_reg_sel(cw['sr2_sel'])

    val1 = If(cw['sr1_sel'] == REG_PC, pc_plus_1, state.read_reg(sr1))
    val2 = If(cw['sr2_sel'] == REG_PC, pc_plus_1, state.read_reg(sr2))

    agu_base = If(cw['agu_base_sel'] == AGU_READ1, val1,
               If(cw['agu_base_sel'] == AGU_READ2, val2,
               If(cw['agu_base_sel'] == AGU_PC, pc_plus_1, BitVecVal(0, WORD_SIZE))))

    agu_index = If(cw['agu_index_sel'] == AGU_READ1, val1,
                If(cw['agu_index_sel'] == AGU_READ2, val2,
                If(cw['agu_index_sel'] == AGU_PC, pc_plus_1, BitVecVal(0, WORD_SIZE))))

    agu_offset = If(cw['agu_offset_sel'] == 1, imm2_ext, imm1_ext)
    agu_address = agu_base + agu_index + agu_offset
    offset = If(cw['imm_sel'] == 1, imm2_ext, imm1_ext)

    # --- EXECUTE STAGE ---
    alu_val1 = If(cw['src1'] == ALU_VAL1, val1,
               If(cw['src1'] == ALU_VAL2, val2,
               If(cw['src1'] == ALU_OFFSET, offset, pc_plus_1)))

    alu_val2 = If(cw['src2'] == ALU_VAL1, val1,
               If(cw['src2'] == ALU_VAL2, val2,
               If(cw['src2'] == ALU_OFFSET, offset, pc_plus_1)))

    alu_result = If(cw['aluop'] == ALU_ADD, alu_val1 + alu_val2,
                 If(cw['aluop'] == ALU_SUB, alu_val1 - alu_val2,
                 If(cw['aluop'] == ALU_NAND, ~(alu_val1 & alu_val2),
                 If(cw['aluop'] == ALU_NEG, -alu_val1,
                 If(cw['aluop'] == ALU_PASSA, alu_val1,
                 If(cw['aluop'] == ALU_PASSB, alu_val2,
                 If(cw['aluop'] == ALU_ADD1, alu_val1 + 1, BitVecVal(0, WORD_SIZE))))))))

    address = If(cw['use_agu'] == 1, agu_address, alu_result)
    mem_data = If(cw['mem_write_source'] == 1, alu_result, val1)

    reg_data = If(cw['memop'] == MEM_READ, mem_read_val, 
               If(cw['memop'] == MEM_WRITE, agu_address, alu_result))

    # --- MEMORY AND WRITEBACK STAGE ---
    final_state = state.with_reg_write(cw['dr_sel'] != REG_IGNORE, dr, reg_data)
    final_state = final_state.with_mem_write(cw['memop'] == MEM_WRITE, address, mem_data)
    final_state = final_state.with_mem_read(cw['memop'] == MEM_READ, address)

    return final_state


# =============================================================================
# SYNTHESIZER ENGINE
# =============================================================================

def solve_opcode_pair(v_op1, v_op2, shared_counter, lock, total_pairs):
    local_rules = {}
    local_report = {} # Key: CW_val -> Value: Set of flag strings
    total_fusions = 0

    for flag_int in range(256):
        unpacker = BitUnpacker(flag_int, 8)
        v_flags = tuple(unpacker.get(1) for _ in range(8))

        # --- SKIP IMPOSSIBLE FLAGS ---
        # 4 & 5: imm1 cannot be strictly < 0 AND strictly > 0
        if v_flags[4] and v_flags[5]: continue 
        # 6 & 7: imm2 cannot be exactly 0 AND exactly 1
        if v_flags[6] and v_flags[7]: continue

        s = Solver()
        # If we can't solve it in 5 seconds, it's probably not solveable
        # So... just quit
        s.set("timeout", 5000) 

        ins1 = {'rx': BitVec('rx1', 4), 'ry': BitVec('ry1', 4), 'rz': BitVec('rz1', 4), 'imm': BitVec('imm1', IMM_SIZE)}
        ins2 = {'rx': BitVec('rx2', 4), 'ry': BitVec('ry2', 4), 'rz': BitVec('rz2', 4), 'imm': BitVec('imm2', IMM_SIZE)}

        pc_val = BitVec('pc', WORD_SIZE)
        mem_read_val = BitVec('mem_read_val', WORD_SIZE)

        sym_vals = {
            'rx1': BitVec('init_rx1', WORD_SIZE), 'ry1': BitVec('init_ry1', WORD_SIZE), 'rz1': BitVec('init_rz1', WORD_SIZE),
            'rx2': BitVec('init_rx2', WORD_SIZE), 'ry2': BitVec('init_ry2', WORD_SIZE), 'rz2': BitVec('init_rz2', WORD_SIZE)
        }

        def init_regs(reg_id):
            return If(reg_id == 0, BitVecVal(0, WORD_SIZE),
                   If(reg_id == ins1['rx'], sym_vals['rx1'],
                   If(reg_id == ins1['ry'], sym_vals['ry1'],
                   If(reg_id == ins1['rz'], sym_vals['rz1'],
                   If(reg_id == ins2['rx'], sym_vals['rx2'],
                   If(reg_id == ins2['ry'], sym_vals['ry2'],
                   If(reg_id == ins2['rz'], sym_vals['rz2'],
                   BitVecVal(0, WORD_SIZE))))))))

        init_state = CPUState(init_regs, BoolVal(False), BitVecVal(0, WORD_SIZE), BitVecVal(0, WORD_SIZE), BoolVal(False), BitVecVal(0, WORD_SIZE), BitVecVal(0, 4))

        # Standard Control Word Variables
        cw = {
            'dr_sel': BitVec('cw_dr_sel', 3), 'sr1_sel': BitVec('cw_sr1_sel', 3), 'sr2_sel': BitVec('cw_sr2_sel', 3),
            'use_agu': BitVec('cw_use_agu', 1), 'agu_base_sel': BitVec('cw_agu_base_sel', 2),
            'agu_index_sel': BitVec('cw_agu_index_sel', 2), 'agu_offset_sel': BitVec('cw_agu_offset_sel', 1),
            'imm_sel': BitVec('cw_imm_sel', 1), 'src1': BitVec('cw_src1', 2), 'src2': BitVec('cw_src2', 2),
            'mem_write_source': BitVec('cw_mem_write_source', 1), 'aluop': BitVec('cw_aluop', 3),
            'memop': BitVec('cw_memop', 2)
        }

        imm1_ext = SignExt(WORD_SIZE - IMM_SIZE, ins1['imm'])
        preconditions = And(
            ins1['rz'] == Extract(3, 0, ins1['imm']),
            ins2['rz'] == Extract(3, 0, ins2['imm']),
            (ins1['rx'] == ins2['ry']) == (v_flags[0] == 1),
            (ins1['rx'] == ins2['rz']) == (v_flags[1] == 1),
            (ins1['rx'] == ins2['rx']) == (v_flags[2] == 1),
            (ins1['rx'] == 13)         == (v_flags[3] == 1), # SP = 13
            (imm1_ext < 0)             == (v_flags[4] == 1),
            (imm1_ext > 0)             == (v_flags[5] == 1),
            (ins2['imm'] == 0)         == (v_flags[6] == 1),
            (ins2['imm'] == 1)         == (v_flags[7] == 1)
        )

        mid_state = execute_sequential_symbolic(v_op1, ins1['rx'], ins1['ry'], ins1['rz'], ins1['imm'], pc_val, mem_read_val, init_state)
        expected_state = execute_sequential_symbolic(v_op2, ins2['rx'], ins2['ry'], ins2['rz'], ins2['imm'], pc_val, mem_read_val, mid_state)
        fused_state = execute_fused(ins1, ins2, cw, pc_val, mem_read_val, init_state)

        # Equivalence checks
        # Must affect relevant registers correctly without touching the other ones
        reg_equiv = And([
            expected_state.read_reg(BitVecVal(i, 4)) == fused_state.read_reg(BitVecVal(i, 4))
            for i in range(1, 16) # Skip 0 since it is hardwired to 0
        ])

        # Must do the same memory operations
        mem_count_equiv = (expected_state.mem_count == fused_state.mem_count)

        mem_write_equiv = And(
            expected_state.mem_write_en == fused_state.mem_write_en,
            Implies(expected_state.mem_write_en, And(
                expected_state.mem_write_addr == fused_state.mem_write_addr,
                expected_state.mem_write_data == fused_state.mem_write_data
            ))
        )

        mem_read_equiv = And(
            expected_state.mem_read_en == fused_state.mem_read_en,
            Implies(expected_state.mem_read_en, expected_state.mem_read_addr == fused_state.mem_read_addr)
        )

        universals = [pc_val, mem_read_val,
                      ins1['rx'], ins1['ry'], ins1['rz'], ins1['imm'], 
                      ins2['rx'], ins2['ry'], ins2['rz'], ins2['imm']
                     ] + list(sym_vals.values()) 

        # Checks all conditions
        s.add(ForAll(universals, Implies(preconditions, And(reg_equiv, mem_write_equiv, mem_read_equiv, mem_count_equiv))))

        # Trim off invalid possiblities
        s.add(cw['dr_sel'] != REG_PC)
        s.add(Implies(cw['memop'] == MEM_IGNORE, cw['use_agu'] == 0))

        # Ensures we don't get useless instructions
        s.add(Or(cw['dr_sel'] != REG_IGNORE, cw['memop'] != MEM_IGNORE))

        if s.check() == sat:
            m = s.model()
            def get_val(key): return m.eval(cw[key], model_completion=True).as_long()

            concrete_cw = build_cw(
                dr_sel=get_val('dr_sel'), sr1_sel=get_val('sr1_sel'), sr2_sel=get_val('sr2_sel'),
                use_agu=get_val('use_agu'), agu_base_sel=get_val('agu_base_sel'),
                agu_index_sel=get_val('agu_index_sel'), agu_offset_sel=get_val('agu_offset_sel'),
                imm_sel=get_val('imm_sel'), src1=get_val('src1'), src2=get_val('src2'),
                mem_write_source=get_val('mem_write_source'), aluop=get_val('aluop'),
                memop=get_val('memop')
            )

            # Key for the ROM: (op1, op2, flag0, ... flag7)
            local_rules[(v_op1, v_op2) + v_flags] = concrete_cw
            
            total_fusions += 1

            # Key for the report
            if concrete_cw not in local_report: local_report[concrete_cw] = []
            local_report[concrete_cw].append("".join(str(bit) for bit in v_flags))

    with lock:
        shared_counter.value += 1
        print(f"({shared_counter.value}/{total_pairs}) Finished {OP_NAMES[v_op1]}, {OP_NAMES[v_op2]} with {len(local_report)} unique fusions (of {total_fusions})!")

    return local_rules, local_report


def run_multicore_synth():
    os.makedirs("./build", exist_ok=True)

    valid_ops = [OP_ADD, OP_NAND, OP_ADDI, OP_LW, OP_SW, OP_LEA]
    pairs = [(o1, o2) for o1 in valid_ops for o2 in valid_ops]
    total_pairs = len(pairs)

    print(f"--- Launching Parallel Synthesis (4 Cores) ---")


    with Manager() as manager:
        shared_counter = manager.Value('i', 0)
        lock = manager.Lock()

        args = [(p[0], p[1], shared_counter, lock, total_pairs) for p in pairs]

        # Using only 4 cores to keep the i5-1135g7 happy
        with Pool(processes=4) as pool:
            results = pool.starmap(solve_opcode_pair, args)

    master_rules = {}
    master_reports = []

    for i, (rules, report) in enumerate(results):
        master_rules.update(rules)
        op1, op2 = pairs[i]
        for cw, flags in report.items():
            master_reports.append((op1, op2, cw, set(flags)))

    print(f"\nSynthesis Complete. Found {len(master_reports)} unique fusions.")

    # --- Write Detailed Report to ./build/ ---
    report_path = "./build/fusion_report.txt"
    with open(report_path, "w") as f:
        f.write("LC-5200b SUPERSCALAR FUSION REPORT\n")
        f.write("==================================\n\n")
        for op1, op2, cw, flags in master_reports:
            f.write(f"[{OP_NAMES[op1]} + {OP_NAMES[op2]}] -> CW: {hex(cw)}\n")
            f.write("Flags (dr_sr1, dr_sr2, waw, is_sp, im1_neg, im1_pos, im2_z, im2_o):\n")
            for compressed in compress_flags(flags):
                f.write(f"  -> {compressed[:4]} {compressed[4:]}\n")
            f.write("-" * 40 + "\n")

    print(f"Detailed report saved to: {report_path}")

    # --- Write ROM Hex ---
    rom_data = []
    for addr in range(65536):
        unpacker = BitUnpacker(addr, 16)
        # This unpacking logic must match ROM address bit-fields
        lookup = tuple(unpacker.get(bits) for bits in [4, 4, 1, 1, 1, 1, 1, 1, 1, 1])
        rom_data.append(master_rules.get(lookup, 0))

    write_verilog_hex("./build/merged_rom.hex", rom_data, bit_width=31)


if __name__ == "__main__":
    run_multicore_synth()

