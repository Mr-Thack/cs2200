module fusion(
    input instruction_data ins1,
    input instruction_data ins2,

    output control_word_t cw
);


// -------------------------------------------------------------------------
// ROM Array Initialization
// -------------------------------------------------------------------------
(* rom_style = "block" *) control_word_t single_rom [16];
(* rom_style = "block" *) control_word_t merged_rom [65536]; // 16 bit entries

// Load from Init ROM
initial begin
    $readmemh("./merged_rom.hex", merged_rom);
end


initial begin
    // 1. Clear everything to safe defaults
    for (int i = 0; i < 16; i++) begin
        single_rom[i].dr_sel   = REG_IGNORE;
        single_rom[i].sr1_sel  = REG_IGNORE;
        single_rom[i].sr2_sel  = REG_IGNORE;
        single_rom[i].imm_sel  = 1'b0;

        single_rom[i].src1     = ALU_VAL1;
        single_rom[i].src2     = ALU_VAL2;
        single_rom[i].aluop    = ALU_IGNORE;
        single_rom[i].cmpop    = CMP_IGNORE;
        single_rom[i].memop    = MEM_IGNORE;
        single_rom[i].logop    = LOGIC_IGNORE;
        single_rom[i].sig_halt = 1'b0;
        single_rom[i].instructions_merged = 1'b0;
    end

    // 2. Define the Control Words
    // OP_ADD
    single_rom[OP_ADD].dr_sel  = REG_RX;
    single_rom[OP_ADD].sr1_sel = REG_RY;
    single_rom[OP_ADD].sr2_sel = REG_RZ;
    single_rom[OP_ADD].aluop   = ALU_ADD;

    // OP_NAND
    single_rom[OP_NAND].dr_sel  = REG_RX;
    single_rom[OP_NAND].sr1_sel = REG_RY;
    single_rom[OP_NAND].sr2_sel = REG_RZ;
    single_rom[OP_NAND].aluop   = ALU_NAND;

    // OP_ADDI
    single_rom[OP_ADDI].dr_sel  = REG_RX;
    single_rom[OP_ADDI].sr1_sel = REG_RY;
    single_rom[OP_ADDI].src2    = ALU_OFFSET;
    single_rom[OP_ADDI].aluop   = ALU_ADD;

    // OP_LW
    single_rom[OP_LW].dr_sel  = REG_RX;
    single_rom[OP_LW].sr1_sel = REG_RY;
    single_rom[OP_LW].src2    = ALU_OFFSET;
    single_rom[OP_LW].aluop   = ALU_ADD;
    single_rom[OP_LW].memop   = MEM_READ;

    // OP_SW
    single_rom[OP_SW].sr1_sel = REG_RX;
    single_rom[OP_SW].sr2_sel = REG_RY;
    single_rom[OP_SW].src1    = ALU_OFFSET;
    single_rom[OP_SW].aluop   = ALU_ADD;
    single_rom[OP_SW].memop   = MEM_WRITE;

    // OP_BEQ
    single_rom[OP_BEQ].sr1_sel = REG_RX;
    single_rom[OP_BEQ].sr2_sel = REG_RY;
    single_rom[OP_BEQ].aluop   = ALU_SUB;
    single_rom[OP_BEQ].cmpop   = CMP_EQ;
    single_rom[OP_BEQ].logop   = LOGIC_JMP_OFFSET;

    // OP_BGT
    single_rom[OP_BGT].sr1_sel = REG_RX;
    single_rom[OP_BGT].sr2_sel = REG_RY;
    single_rom[OP_BGT].aluop   = ALU_SUB;
    single_rom[OP_BGT].cmpop   = CMP_GT;
    single_rom[OP_BGT].logop   = LOGIC_JMP_OFFSET;

    // OP_JALR
    single_rom[OP_JALR].dr_sel  = REG_RY;
    single_rom[OP_JALR].sr1_sel = REG_RX;
    single_rom[OP_JALR].aluop   = ALU_PASSA;
    single_rom[OP_JALR].src1    = ALU_PC;
    single_rom[OP_JALR].logop   = LOGIC_JMP_RES;

    // OP_LEA
    single_rom[OP_LEA].dr_sel = REG_RX;
    single_rom[OP_LEA].src1   = ALU_PC;
    single_rom[OP_LEA].src2   = ALU_OFFSET;
    single_rom[OP_LEA].aluop  = ALU_ADD;

    // OP_HALT
    single_rom[OP_HALT].sig_halt = 1'b1;
end


// -------------------------------------------------------------------------
// Physical Decode Logic
// -------------------------------------------------------------------------
logic [19:0] imm1_val, imm2_val;
assign imm1_val = ins1.imm;
assign imm2_val = ins2.imm;

// 8 Flags
logic raw_dr_sr1, raw_dr_sr2, waw_dr_dr, is_sp;
logic imm1_neg, imm1_pos, imm2_zero, imm2_one;

assign raw_dr_sr1 = (ins1.rx == ins2.ry);
assign raw_dr_sr2 = (ins1.rx == ins2.imm.rz); 
assign waw_dr_dr  = (ins1.rx == ins2.rx);
assign is_sp      = (ins1.rx == 4'd13); // $sp is register 13

assign imm1_neg   = imm1_val[19]; // MSB indicates negative in 20-bit 2's complement
assign imm1_pos   = (!imm1_val[19] && imm1_val != 20'd0);
assign imm2_zero  = (imm2_val == 20'd0);
assign imm2_one   = (imm2_val == 20'd1);

// 16-bit Index for the Merger ROM
logic [15:0] merge_index;
assign merge_index = {
    ins1.opcode,  // Bits [15:12]
    ins2.opcode,  // Bits [11:8]
    raw_dr_sr1,   // Bit 7
    raw_dr_sr2,   // Bit 6
    waw_dr_dr,    // Bit 5
    is_sp,        // Bit 4
    imm1_neg,     // Bit 3
    imm1_pos,     // Bit 2
    imm2_zero,    // Bit 1
    imm2_one      // Bit 0
};


// ----------------------
// Control Word Selection
// ----------------------

control_word_t cw_single, cw_merged;
logic [1:0] instructions_merged;

assign cw_single = single_rom[ins1.opcode];
assign cw_merged = merged_rom[merge_index];

// If no merge available, go back to single:
always_comb begin
    cw = (cw_merged == '0) ? cw_single : cw_merged;
    cw.instructions_merged = (cw_merged == '0) ? 2'd0 : 2'd1;
end

endmodule
