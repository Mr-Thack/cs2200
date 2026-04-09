import types::*;

module decode(
    input logic clk,
    input logic rst,

    input logic branch_true,
    input logic halt_now,

    input fbuf_data fbuf,

    input [31:0] dout1,
    input [31:0] dout2,
    
    output dbuf_data dbuf
);


instruction_data ins;
assign ins = (rst || branch_true || halt_now) ? '0 : fbuf.instruction;
// Create Bubble (NOOP) when branch taken or stalled

logic is_immediate;

// sr1 and sr2 are the input registers for the DPRF
// and dout1 and dout2 are the output ports for them
// these douts will then be forwarded as the inputs to the ALU
// dr is just the desination register,
// which'll be forwarded to the memory stage
logic [3:0] dr, sr1, sr2; 

always_comb begin
    // This is for remaping which registers are:
    // 1. Desination Register (the one we write to)
    // 2. Source Registers (the ones whose data we need)
    //
    // Since we can read 2 things at once,
    // but can only write to 1 thing at a time...
    case (ins.opcode)
        // Ok, this is hardcoded,
        // but I just don't care...
        // lol I probably shouldn't say that

        // R-Type Instructions
        OP_ADD, OP_NAND, OP_MIN, OP_MAX: begin
            dr = ins.rx;
            sr1 = ins.ry;
            sr2 = ins.imm.rz;
        end 

        // if we didn't execute the previous block, then: //
        // IMMEDIATE INSTRUCTIONS //

        // I-Type with RX as DR.
        OP_ADDI, OP_LW: begin
            dr = ins.rx;
            sr1 = ins.ry;
            sr2 = '0; // unused
        end

        OP_JALR: begin
            dr = ins.ry;
            sr1 = ins.rx;
            sr2 = '0; // unused
        end

        // I-Type with 2 Sources (no DR)
        OP_SW, OP_BEQ, OP_BGT: begin
            // BEQ and BGT will compare the result,
            // And SW needs to read RX,
            // but will only use RY + OFFSET on the ALU
            dr = '0; // unused
            sr1 = ins.rx; 
            sr2 = ins.ry;
        end

        OP_LEA: begin
            dr = ins.rx;
            sr1 = '0;
            sr2 = '0;
        end

        OP_HALT: begin
            dr = '0;
            sr1 = '0;
            sr2 = '0;
        end

        // If we didn't explicitly set an instruction, FAIL
        // So that we know we forgot to implement something...
        default: begin
            dr = 'X;
            sr1 = 'X;
            sr2 = 'X;
        end
    endcase
end

logic [19:0] imm_wire;

always_comb begin
    // Pass everything important along and let the EXECUTE Stage figure out
    // what it wants to do with our stuff
    dbuf.pc_plus_1 = fbuf.pc_plus_1;
    dbuf.opcode = ins.opcode;
    dbuf.dr = dr;

    dbuf.val1 = dout1;
    dbuf.sr1 = sr1;

    dbuf.val2 = dout2;
    dbuf.sr2 = sr2;

    imm_wire = ins.imm;

    dbuf.offset = { {12{imm_wire[19]}}, imm_wire };
end

endmodule
