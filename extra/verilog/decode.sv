import types::*;

module decode(
    input logic clk,
    input logic rst,

    input logic exec_branch_taken,
    input logic stall_now,
    input logic halt_now,

    input fbuf_data fbuf,

    output sig_halt,

    output dbuf_data dbuf,

    input [31:0] dout1,
    input [31:0] dout2,

    input [31:0] jalr_target_fwd,

    output logic ras_push,
    output logic [31:0] ras_push_data,
    output logic ras_recover,

    output logic decode_branch_taken,
    output logic [31:0] decode_branch_target
);

instruction_data ins1, ins2;
control_word_t cw;

// Create Bubble (NOOP) when exec branch taken or stalled
always_comb begin
    if (rst || exec_branch_taken || halt_now) begin
        ins1 = '0;
        ins2 = '0;
        cw = '0;
    end else begin
        ins1 = fbuf.ins1;
        ins2 = fbuf.ins2;
        cw = fbuf.cw;
    end
end


logic [3:0] dr, sr1, sr2; 
alu_source src1, src2;
alu_operation aluop;
cmp_operation cmpop;
mem_operation memop;
logic_operation logop;

assign ras_recover = exec_branch_taken && fbuf.ras_was_popped;

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
        REG_RX:  dr = ins1.rx;
        REG_RY:  dr = ins1.ry;
        REG_RZ:  dr = ins1.imm.rz;
        REG_INS2_RX:  dr = ins2.rx;
        REG_INS2_RY:  dr = ins2.ry;
        REG_INS2_RZ:  dr = ins2.imm.rz;
        default: dr = '0;
    endcase

    // 3. MUX Source Register 1
    case (cw.sr1_sel)
        REG_RX:  sr1 = ins1.rx;
        REG_RY:  sr1 = ins1.ry;
        REG_RZ:  sr1 = ins1.imm.rz;
        REG_INS2_RX:  sr1 = ins2.rx;
        REG_INS2_RY:  sr1 = ins2.ry;
        REG_INS2_RZ:  sr1 = ins2.imm.rz;
        default: sr1 = '0;
    endcase

    // 4. MUX Source Register 2
    case (cw.sr2_sel)
        REG_RX:  sr2 = ins1.rx;
        REG_RY:  sr2 = ins1.ry;
        REG_RZ:  sr2 = ins1.imm.rz;
        REG_INS2_RX:  sr2 = ins2.rx;
        REG_INS2_RY:  sr2 = ins2.ry;
        REG_INS2_RZ:  sr2 = ins2.imm.rz;
        default: sr2 = '0;
    endcase
   
    ras_push = 1'b0;
    ras_push_data = fbuf.pc_plus_1;
    decode_branch_taken = 1'b0;
    decode_branch_target = 'X;
    if (logop == LOGIC_JMP_RES) begin
        if (dr != 4'd0 && !exec_branch_taken && !stall_now) begin
            ras_push = 1'b1;
        end

        // Evaluate our prediction
        if (!fbuf.predicted_taken || jalr_target_fwd != fbuf.predict_target) begin
            decode_branch_taken = 1'b1;
            decode_branch_target = jalr_target_fwd;
        end
    end

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

    imm_wire = cw.imm_sel ? ins2.imm : ins1.imm;

    dbuf.offset = { {12{imm_wire[19]}}, imm_wire };

    dbuf.aluop = cw.aluop;
    dbuf.cmpop = cw.cmpop;
    dbuf.memop = cw.memop;
    dbuf.logop = cw.logop;

    dbuf.predicted_taken = fbuf.predicted_taken;

    dbuf.btb_hit = fbuf.btb_hit;
    dbuf.valid = fbuf.valid; 

    dbuf.instructions_merged = cw.instructions_merged; 
end

endmodule
