import types::*;

// --------------------------------
// Types & Control Word Definition
// --------------------------------
typedef enum logic [1:0] {
    REG_IGNORE = 2'b00,
    REG_RX     = 2'b01,
    REG_RY     = 2'b10,
    REG_RZ     = 2'b11
} reg_sel_t;

typedef struct packed {
    reg_sel_t       dr_sel;
    reg_sel_t       sr1_sel;
    reg_sel_t       sr2_sel;

    alu_source      src1;
    alu_source      src2;
    alu_operation   aluop;
    cmp_operation   cmpop;
    mem_operation   memop;
    logic_operation logop;
    logic           sig_halt;
} control_word_t;


module decode(
    input logic clk,
    input logic rst,

    input logic branch_taken,
    input logic halt_now,

    input fbuf_data fbuf,

    input [31:0] dout1,
    input [31:0] dout2,

    output sig_halt,

    output dbuf_data dbuf
);



// -------------------------------------------------------------------------
// ROM Array Initialization
// -------------------------------------------------------------------------
(* rom_style = "block" *) control_word_t decode_rom [16];

initial begin
    // 1. Clear everything to safe defaults
    for (int i = 0; i < 16; i++) begin
        decode_rom[i].dr_sel   = REG_IGNORE;
        decode_rom[i].sr1_sel  = REG_IGNORE;
        decode_rom[i].sr2_sel  = REG_IGNORE;
        decode_rom[i].src1     = ALU_VAL1;
        decode_rom[i].src2     = ALU_VAL2;
        decode_rom[i].aluop    = ALU_IGNORE;
        decode_rom[i].cmpop    = CMP_IGNORE;
        decode_rom[i].memop    = MEM_IGNORE;
        decode_rom[i].logop    = LOGIC_IGNORE;
        decode_rom[i].sig_halt = 1'b0;
    end

    // 2. Define the Control Words
    // OP_ADD
    decode_rom[OP_ADD].dr_sel  = REG_RX;
    decode_rom[OP_ADD].sr1_sel = REG_RY;
    decode_rom[OP_ADD].sr2_sel = REG_RZ;
    decode_rom[OP_ADD].aluop   = ALU_ADD;

    // OP_NAND
    decode_rom[OP_NAND].dr_sel  = REG_RX;
    decode_rom[OP_NAND].sr1_sel = REG_RY;
    decode_rom[OP_NAND].sr2_sel = REG_RZ;
    decode_rom[OP_NAND].aluop   = ALU_NAND;

    // OP_ADDI
    decode_rom[OP_ADDI].dr_sel  = REG_RX;
    decode_rom[OP_ADDI].sr1_sel = REG_RY;
    decode_rom[OP_ADDI].src2    = ALU_OFFSET;
    decode_rom[OP_ADDI].aluop   = ALU_ADD;

    // OP_LW
    decode_rom[OP_LW].dr_sel  = REG_RX;
    decode_rom[OP_LW].sr1_sel = REG_RY;
    decode_rom[OP_LW].src2    = ALU_OFFSET;
    decode_rom[OP_LW].aluop   = ALU_ADD;
    decode_rom[OP_LW].memop   = MEM_READ;

    // OP_SW
    decode_rom[OP_SW].sr1_sel = REG_RX;
    decode_rom[OP_SW].sr2_sel = REG_RY;
    decode_rom[OP_SW].src1    = ALU_OFFSET;
    decode_rom[OP_SW].aluop   = ALU_ADD;
    decode_rom[OP_SW].memop   = MEM_WRITE;

    // OP_BEQ
    decode_rom[OP_BEQ].sr1_sel = REG_RX;
    decode_rom[OP_BEQ].sr2_sel = REG_RY;
    decode_rom[OP_BEQ].aluop   = ALU_SUB;
    decode_rom[OP_BEQ].cmpop   = CMP_EQ;
    decode_rom[OP_BEQ].logop   = LOGIC_JMP_OFFSET;

    // OP_BGT
    decode_rom[OP_BGT].sr1_sel = REG_RX;
    decode_rom[OP_BGT].sr2_sel = REG_RY;
    decode_rom[OP_BGT].aluop   = ALU_SUB;
    decode_rom[OP_BGT].cmpop   = CMP_GT;
    decode_rom[OP_BGT].logop   = LOGIC_JMP_OFFSET;

    // OP_JALR
    decode_rom[OP_JALR].dr_sel  = REG_RY;
    decode_rom[OP_JALR].sr1_sel = REG_RX;
    decode_rom[OP_JALR].aluop   = ALU_PASSA;
    decode_rom[OP_JALR].logop   = LOGIC_JMP_RES;

    // OP_LEA
    decode_rom[OP_LEA].dr_sel = REG_RX;
    decode_rom[OP_LEA].src1   = ALU_PC;
    decode_rom[OP_LEA].src2   = ALU_OFFSET;
    decode_rom[OP_LEA].aluop  = ALU_ADD;

    // OP_HALT
    decode_rom[OP_HALT].sig_halt = 1'b1;
end


// -------------------------------------------------------------------------
// Physical Decode Logic
// -------------------------------------------------------------------------
instruction_data ins;
// Create Bubble (NOOP) when branch taken or stalled
assign ins = (rst || branch_taken || halt_now) ? '0 : fbuf.instruction;

logic [3:0] dr, sr1, sr2; 
alu_source src1, src2;
alu_operation aluop;
cmp_operation cmpop;
mem_operation memop;
logic_operation logop;

control_word_t cw;
assign cw = decode_rom[ins.opcode];

always_comb begin
    // 1. Route the signals directly from the ROM Control Word
    src1  = cw.src1;
    src2  = cw.src2;
    aluop = cw.aluop;
    cmpop = cw.cmpop;
    memop = cw.memop;
    logop = cw.logop;

    // Ensure hard reset overrides whatever is fetched from the ROM
    sig_halt = rst ? 1'b1 : cw.sig_halt;

    // 2. MUX the Destination Register
    case (cw.dr_sel)
        REG_RX:  dr = ins.rx;
        REG_RY:  dr = ins.ry;
        REG_RZ:  dr = ins.imm.rz;
        default: dr = '0;
    endcase

    // 3. MUX Source Register 1
    case (cw.sr1_sel)
        REG_RX:  sr1 = ins.rx;
        REG_RY:  sr1 = ins.ry;
        REG_RZ:  sr1 = ins.imm.rz;
        default: sr1 = '0;
    endcase

    // 4. MUX Source Register 2
    case (cw.sr2_sel)
        REG_RX:  sr2 = ins.rx;
        REG_RY:  sr2 = ins.ry;
        REG_RZ:  sr2 = ins.imm.rz;
        default: sr2 = '0;
    endcase
end

// -------------------------------------------------------------------------
// Execution Buffer Forwarding
// -------------------------------------------------------------------------
logic [19:0] imm_wire;

always_comb begin
    // Pass everything important along and let the EXECUTE Stage figure out
    // what it wants to do with our stuff
    dbuf.pc_plus_1 = fbuf.pc_plus_1;
    dbuf.dr = dr;

    dbuf.val1 = dout1;
    dbuf.sr1 = sr1;
    dbuf.src1 = src1;

    dbuf.val2 = dout2;
    dbuf.sr2 = sr2;
    dbuf.src2 = src2;

    imm_wire = ins.imm;

    dbuf.offset = { {12{imm_wire[19]}}, imm_wire };

    dbuf.aluop = aluop;
    dbuf.cmpop = cmpop;
    dbuf.memop = memop;
    dbuf.logop = logop;

    dbuf.predicted_taken = fbuf.predicted_taken;

    dbuf.btb_hit = fbuf.btb_hit;
    dbuf.valid = fbuf.valid; 
end

endmodule
