import types::*;

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


instruction_data ins;
assign ins = (rst || branch_taken || halt_now) ? '0 : fbuf.instruction;
// Create Bubble (NOOP) when branch taken or stalled

// sr1 and sr2 are the input registers for the DPRF
// and dout1 and dout2 are the output ports for them
// these douts will then be forwarded as the inputs to the ALU
// dr is just the desination register,
// which'll be forwarded to the memory stage
logic [3:0] dr, sr1, sr2; 
alu_source src1, src2;
alu_operation aluop;
cmp_operation cmpop;
mem_operation memop;
logic_operation logop;

always_comb begin
    // This is for remaping which registers are:
    // 1. Desination Register (the one we write to)
    // 2. Source Registers (the ones whose data we need)
    //
    // Since we can read 2 things at once,
    // but can only write to 1 thing at a time...

    dr = '0;
    sr1 = '0;
    sr2 = '0;

    src1 = ALU_VAL1;
    src2 = ALU_VAL2;

    aluop = ALU_IGNORE;
    cmpop = CMP_IGNORE;
    logop = LOGIC_IGNORE;
    memop = MEM_IGNORE;

    sig_halt = rst ? 1'b1 : '0;

    unique case (ins.opcode)
        // Ok, this is hardcoded,
        // but I just don't care...
        // lol I probably shouldn't say that

        // R-Type Instructions
        OP_ADD, OP_NAND: begin
            dr = ins.rx;
            sr1 = ins.ry;
            sr2 = ins.imm.rz;

            aluop = (ins.opcode == OP_ADD) ? ALU_ADD : ALU_NAND;
        end 

        // if we didn't execute the previous block, then: //
        // IMMEDIATE INSTRUCTIONS //

        // I-Type with RX as DR.
        OP_ADDI, OP_LW: begin
            dr = ins.rx;
            sr1 = ins.ry;
            src2 = ALU_OFFSET;
            aluop = ALU_ADD;

            if (ins.opcode == OP_LW) begin
                memop = MEM_READ;
            end
        end

        OP_JALR: begin
            dr = ins.ry;
            sr1 = ins.rx;
            aluop = ALU_PASSA;
            logop = LOGIC_JMP_RES;
        end

        // I-Type with 2 Sources (no DR)
        OP_BEQ, OP_BGT: begin
            // BEQ and BGT will compare the result
            sr1 = ins.rx; 
            sr2 = ins.ry;
            aluop = ALU_SUB;                
            cmpop = (ins.opcode == OP_BEQ)? CMP_EQ : CMP_GT;
            logop = LOGIC_JMP_OFFSET;
        end
        
        // I-Type with 2 Sources (no DR)
        OP_SW: begin
            // And SW needs to read RX,
            // but will only use RY + OFFSET on the ALU
            sr1 = ins.rx;
            sr2 = ins.ry;
            src1 = ALU_OFFSET;
            aluop = ALU_ADD;
            memop = MEM_WRITE;
        end

        OP_LEA: begin
            dr = ins.rx;
            src1 = ALU_PC;
            src2 = ALU_OFFSET;
            aluop = ALU_ADD;
        end

        OP_HALT: begin
            sig_halt = 1'b1;
            dr = '0;
            sr1 = '0;
            sr2 = '0;
        end
    endcase
end

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
