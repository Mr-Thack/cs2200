import types::*;

module pipeline(
    input logic clk,
    input logic rst
);

// Everything is defined left to right

// ************ //
// GLOBAL LOGIC //
// ************ //

logic [31:0] PC;

logic stall_now;

logic branch_true;
logic [31:0] branch_target_line;

logic [3:0] write_reg_dest;
logic [31:0] write_reg_data;


fbuf_data fbuf_in, fbuf_out;
dbuf_data dbuf_in, dbuf_out;
ebuf_data ebuf_in, ebuf_out;
mbuf_data mbuf_in, mbuf_out;

always_ff @(posedge clk) begin
    if (rst) begin
        stall_now <= 1'b0;
    end else if (dbuf_out.opcode == OP_HALT) begin
        // As soon as we get HALT in the exec stage,
        // latch onto the STALL forever and forever.
        stall_now <= 1'b1;
    end

    if (rst) begin
        PC <= 32'd0;
    end else if (!stall_now) begin
        // We ONLY want to change PC if we're not Stalled
        PC <= branch_true? branch_target_line : (PC + 1);
    end
end


// *********** //
// FETCH STAGE //
// *********** //

// This wire is the output from imem
logic [31:0] instruction_read_line;

mem #(.INIT("../pow.hex")) imem (
    .clk(clk),
    .rst(rst),
    .we(1'b0),
    .addr(PC[15:0]),
    .write_data('0),
    .read_data(instruction_read_line)
);

always_comb begin
    fbuf_in.pc_plus_1 = PC + 1;
    fbuf_in.instruction = instruction_read_line;
end

always_ff @(posedge clk) begin
    // If Stalled,
    // then we can't forward our newly fetched instruction to the Decode Stage
    if (!stall_now) begin
        fbuf_out <= (rst || branch_true) ? '0 : fbuf_in;
    end
end


// ************ //
// DECODE STAGE //
// ************ //

instruction_data ins;
assign ins = (rst || branch_true || stall_now) ? '0 : fbuf_out.instruction;
// Create Bubble (NOOP) when branch taken or stalled

logic is_immediate;

// sr1 and sr2 are the input registers for the DPRF
// and dout1 and dout2 are the output ports for them
// these douts will then be forwarded as the inputs to the ALU
// dr is just the desination register,
// which'll be forwarded to the memory stage
logic [3:0] dr, sr1, sr2; 
logic [31:0] dout1, dout2;

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

// Physically instantiate and read/write registers
dprf registers (
    .clk(clk),
    .rst(rst),
    .we('1),
    .regno_read1(sr1),
    .regno_read2(sr2),
    .regno_write(write_reg_dest),
    .write_data(write_reg_data),
    .read_data1(dout1),
    .read_data2(dout2)
);


logic [19:0] imm_wire;

always_comb begin
    // Pass everything important along and let the EXECUTE Stage figure out
    // what it wants to do with our stuff
    dbuf_in.pc_plus_1 = fbuf_out.pc_plus_1;
    dbuf_in.opcode = ins.opcode;
    dbuf_in.dr = dr;

    // So... we need to do Data Forwarding
    // But ummm.... as of the time I'm writing, I'm too tired to modularize
    // So, remember to copy and paste and edit properly!!!
    dbuf_in.val1 = dout1;
    dbuf_in.sr1 = sr1;

    dbuf_in.val2 = dout2;
    dbuf_in.sr2 = sr2;

    imm_wire = ins.imm;

    dbuf_in.offset = { {12{imm_wire[19]}}, imm_wire };
end

always_ff @(posedge clk) begin
    dbuf_out <= (rst || stall_now || (dbuf_out.opcode == OP_HALT)) ? '0 : dbuf_in;
end

// DEBUGGGING //
logic [31:0] debug_dbuf_pc;     assign debug_dbuf_pc     = dbuf_out.pc_plus_1;
opcode_t     debug_dbuf_op;     assign debug_dbuf_op     = dbuf_out.opcode;
logic [3:0]  debug_dbuf_dr;     assign debug_dbuf_dr     = dbuf_out.dr;
logic [31:0] debug_dbuf_val1;   assign debug_dbuf_val1   = dbuf_out.val1;
logic [31:0] debug_dbuf_val2;   assign debug_dbuf_val2   = dbuf_out.val2;
logic [31:0] debug_dbuf_offset; assign debug_dbuf_offset = dbuf_out.offset;

// ************* //
// EXECUTE STAGE //
// ************* //


operation aluop;
logic [31:0] alu_val1;
logic [31:0] alu_val2;
logic [31:0] alu_result;

// We need to calculate the forwarded values
// And we might overwrite the alu_val's
// But then use the forwarded values later / elsewhere (like in SW)
// So, we need to keep these separate.
logic [31:0] fwd_val1;
logic [31:0] fwd_val2;

always_comb begin
    fwd_val1 = dbuf_out.val1;
    fwd_val2 = dbuf_out.val2;
    
    // 1. Check Results of Memory Stage First (older data, so lower priority)
    if ((mbuf_out.dr != 4'd0) && (mbuf_out.dr == dbuf_out.sr1)) begin
        fwd_val1 = mbuf_out.data;
    end
    if ((mbuf_out.dr != 4'd0) && (mbuf_out.dr == dbuf_out.sr2)) begin
        fwd_val2 = mbuf_out.data;
    end

    // 2. Check Results of Execute Stage Second (newer data, so higher priority)
    // Overwrites any forwarding from the memory stage
    if ((ebuf_out.dr != 4'd0) && (ebuf_out.dr == dbuf_out.sr1)) begin
        fwd_val1 = ebuf_out.data;
    end
    if ((ebuf_out.dr != 4'd0) && (ebuf_out.dr == dbuf_out.sr2)) begin
        fwd_val2 = ebuf_out.data;
    end

    alu_val1 = fwd_val1;
    alu_val2 = fwd_val2;


    case (dbuf_out.opcode)
        OP_ADD, OP_JALR: begin
            aluop = ADD;
        end

        OP_ADDI, OP_LW: begin
            aluop = ADD;
            alu_val2 = dbuf_out.offset;
        end

        OP_SW: begin
            aluop = ADD;
            alu_val1 = dbuf_out.offset;
        end

        OP_NAND: begin
            aluop = NAND;
        end

        OP_BEQ, OP_BGT, OP_MIN, OP_MAX: begin
            aluop = SUB; 
        end

        OP_HALT: begin
            aluop = IGNORE;
        end

        OP_LEA: begin
            aluop= ADD;
            alu_val1 = dbuf_out.pc_plus_1;
            alu_val2 = dbuf_out.offset;
        end

        default: begin
            aluop = IGNORE;
        end
    endcase
end

alu alu0 (
    .a(alu_val1),
    .b(alu_val2),
    .op(aluop),
    .out(alu_result)
);

always_comb begin
    branch_true = 1'b0;
    branch_target_line = dbuf_out.pc_plus_1 + dbuf_out.offset;
    
    ebuf_in.opcode = dbuf_out.opcode;

    ebuf_in.dr = '0;
    ebuf_in.address = '0;
    ebuf_in.data = '0;
    
    case (dbuf_out.opcode)
        OP_ADD, OP_NAND, OP_ADDI, OP_LEA: begin
            ebuf_in.dr = dbuf_out.dr;
            ebuf_in.data = alu_result;
        end

        OP_LW: begin
            ebuf_in.dr = dbuf_out.dr;
            ebuf_in.address = alu_result;
        end

        OP_SW: begin
            ebuf_in.address = alu_result;
            ebuf_in.data = fwd_val1;
        end

        OP_BEQ: begin
            branch_true = (alu_result == 0);
        end

        OP_JALR: begin
            ebuf_in.dr = dbuf_out.dr;
            ebuf_in.data = dbuf_out.pc_plus_1;
            branch_target_line = alu_result;
            branch_true = 1'b1;
        end

        OP_BGT: begin
            branch_true = ($signed(alu_result) > 0);
        end

        OP_MIN: begin
            ebuf_in.dr = dbuf_out.dr;
            ebuf_in.data = ($signed(alu_result) < 0) ? fwd_val1 : fwd_val2;
        end
        
        OP_MAX: begin
            ebuf_in.dr = dbuf_out.dr;
            ebuf_in.data = ($signed(alu_result) > 0) ? fwd_val1 : fwd_val2;
        end

    endcase
end

always_ff @(posedge clk) begin
    ebuf_out <= rst ? '0 : ebuf_in;
end

// ********* //
// MEM STAGE //
// ********* //

logic we_dmem;
logic [31:0] data_read_line;
logic [31:0] data_write_dmem;

always_comb begin
    we_dmem = (ebuf_out.opcode == OP_SW);
    data_write_dmem = ebuf_out.data;
end

mem #(.INIT("../pow.hex")) dmem (
    .clk(clk),
    .rst(rst),
    .we(we_dmem),
    .addr(ebuf_out.address[15:0]),
    .write_data(data_write_dmem),
    .read_data(data_read_line)
);

always_comb begin
    mbuf_in.dr = ebuf_out.dr;
    mbuf_in.data = '0;

    case (ebuf_out.opcode)
        OP_ADD, OP_NAND, OP_ADDI, OP_JALR, OP_LEA, OP_MIN, OP_MAX: begin
            mbuf_in.data = ebuf_out.data;
        end

        OP_LW: begin
            mbuf_in.data = data_read_line;
        end

        default: begin
            // SW, BEQ, HALT, BGT 
            mbuf_in.dr = '0;
            // Just in case...
        end
    endcase
end

always_ff @(posedge clk) begin
    mbuf_out <= rst? '0 : mbuf_in;
end

// **************** //
// WRITE BACK STAGE //
// **************** //

always_comb begin
   write_reg_dest = mbuf_out.dr;
   write_reg_data = mbuf_out.data;
end

endmodule
