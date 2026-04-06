import types::*;

module pipeline(
    input logic clk,
    input logic rst,

    output logic [31:0] debug_pc,
    output logic halt_flag,
    output logic [31:0] out_stat_cycles
);

// Everything is defined left to right

// ************ //
// GLOBAL LOGIC //
// ************ //

logic [31:0] PC;

// Stop forever for halting
logic halt_now;
// Stop for a load-use hazard
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
        halt_now <= 1'b0;
    end else if (dbuf_out.opcode == OP_HALT) begin
        // As soon as we get HALT in the exec stage,
        // latch onto the STALL forever and forever.
        halt_now <= 1'b1;
    end

    if (rst) begin
        PC <= 32'd0;
    end else if (!halt_now && !stall_now) begin
        // We ONLY want to change PC if we're not Stalled
        PC <= branch_true? branch_target_line : (PC + 1);
    end
end

// ********** //
// PERF STATS //
// ********** //
logic [31:0] stat_cycles;
logic [31:0] stat_stalls;
logic [31:0] stat_flushes;
logic [31:0] stat_branches_seen;
logic [31:0] stat_branches_correct;
logic [31:0] stat_branches_incorrect;

always_ff @(posedge clk) begin
    if (rst) begin
        stat_cycles <= '0;
        stat_stalls <= '0;
        stat_flushes <= '0;
        stat_branches_seen <= '0;
        stat_branches_correct <= '0;
        stat_branches_incorrect <= '0;
    end else begin
        if (!halt_now) stat_cycles <= stat_cycles + 1;

        if (stall_now) stat_stalls <= stat_stalls + 1;

        // If branch_true, then our policy of predicting not taken was wrong
        if (branch_true) stat_flushes <= stat_flushes + 1;

        if (dbuf_out.opcode == OP_BEQ || dbuf_out.opcode == OP_BGT) begin
            stat_branches_seen <= stat_branches_seen + 1;
            // If not branch_true, then we were correct in prredicting not taken
            if (!branch_true) stat_branches_correct <= stat_branches_correct + 1;

            stat_branches_incorrect = stat_branches_seen - stat_branches_correct;
        end
    end
end

// These are here to force Yosys to compile this module
assign debug_pc = PC;
assign halt_flag = halt_now;
assign out_stat_cycles = stat_cycles;

// ********************* //
// INLINED MEMORY ARRAYS //
// ********************* //
localparam MEM_SIZE = 2**16;

(* nomem2reg *) logic [31:0] IMEM [MEM_SIZE];
(* nomem2reg *) logic [31:0] DMEM [MEM_SIZE];

// Load from Init ROM
initial begin
    $readmemh("../pow.hex", IMEM);
    $readmemh("../pow.hex", DMEM);
end

// *********** //
// FETCH STAGE //
// *********** //

// This wire is the output from imem
logic [31:0] instruction_read_line;


assign instruction_read_line = IMEM[PC[15:0]];


always_comb begin
    fbuf_in.pc_plus_1 = PC + 1;
    fbuf_in.instruction = instruction_read_line;
end

always_ff @(posedge clk) begin
    // If Stalled,
    // then we can't forward our newly fetched instruction to the Decode Stage
    if (!halt_now && !stall_now) begin
        fbuf_out <= (rst || branch_true) ? '0 : fbuf_in;
    end
end


// ************ //
// DECODE STAGE //
// ************ //

instruction_data ins;
assign ins = (rst || branch_true || halt_now) ? '0 : fbuf_out.instruction;
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


assign stall_now = (dbuf_out.dr != 4'd0) && (dbuf_out.opcode == OP_LW)
                    && ((dbuf_out.dr == sr1) || (dbuf_out.dr == sr2));


logic [19:0] imm_wire;

always_comb begin
    // Pass everything important along and let the EXECUTE Stage figure out
    // what it wants to do with our stuff
    dbuf_in.pc_plus_1 = fbuf_out.pc_plus_1;
    dbuf_in.opcode = ins.opcode;
    dbuf_in.dr = dr;

    dbuf_in.val1 = dout1;
    dbuf_in.sr1 = sr1;

    dbuf_in.val2 = dout2;
    dbuf_in.sr2 = sr2;

    imm_wire = ins.imm;

    dbuf_in.offset = { {12{imm_wire[19]}}, imm_wire };
end

always_ff @(posedge clk) begin
    // Need to check halt_now and dbuf_out.opcode because
    // halt_now is only latched on the clock cycle, so it wouldn't propogate
    // fast enough to prevent the decode stage from forwarding this
    dbuf_out <= (rst || halt_now || stall_now || (dbuf_out.opcode == OP_HALT)) ? '0 : dbuf_in;
end

// FOR DEBUGGGING //
logic [31:0]    debug_dbuf_pc;     assign debug_dbuf_pc     = dbuf_out.pc_plus_1;
opcode_t debug_dbuf_op;     assign debug_dbuf_op     = dbuf_out.opcode;
logic [3:0]     debug_dbuf_dr;     assign debug_dbuf_dr     = dbuf_out.dr;
logic [31:0]    debug_dbuf_val1;   assign debug_dbuf_val1   = dbuf_out.val1;
logic [31:0]    debug_dbuf_val2;   assign debug_dbuf_val2   = dbuf_out.val2;
logic [31:0]    debug_dbuf_offset; assign debug_dbuf_offset = dbuf_out.offset;

// ************* //
// EXECUTE STAGE //
// ************* //


alu_operation aluop;
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
    
    // So... we need to do Data Forwarding
    // But ummm.... as of the time I'm writing, I'm too tired to modularize
    // So, remember to copy and paste and edit properly!!!

    // Also, the diagram put this before the DBUF,
    // but we're doing this afterwards and overwriting the data from dbuf
    // because the data is latched at the end of the cycle,
    // so we would want to wait until after the EX and MEM stages are done,
    // so that they can latch their data into the buffer and then we forward.
    // Oh wait, I could have also checked mbuf_in and ebuf_in instead...
    // Then I could've done what the diagram did and forward at the end of the
    // decode stage before the execute stage.
    // Oh well! This works and I don't care anymore!

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
            aluop = ALU_ADD;
        end

        OP_ADDI, OP_LW: begin
            aluop = ALU_ADD;
            alu_val2 = dbuf_out.offset;
        end

        OP_SW: begin
            aluop = ALU_ADD;
            alu_val1 = dbuf_out.offset;
        end

        OP_NAND: begin
            aluop = ALU_NAND;
        end

        OP_BEQ, OP_BGT, OP_MIN, OP_MAX: begin
            aluop = ALU_SUB; 
        end

        OP_HALT: begin
            aluop = ALU_IGNORE;
        end

        OP_LEA: begin
            aluop= ALU_ADD;
            alu_val1 = dbuf_out.pc_plus_1;
            alu_val2 = dbuf_out.offset;
        end

        default: begin
            aluop = ALU_IGNORE;
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

assign data_read_line = DMEM[ebuf_out.address[15:0]];

always_comb begin
    we_dmem = (ebuf_out.opcode == OP_SW);
    data_write_dmem = ebuf_out.data;
end

always_ff @(posedge clk) begin
    if (we_dmem) begin
        DMEM[ebuf_out.address[15:0]] <= data_write_dmem;
    end
end

always_comb begin
    mbuf_in.dr = ebuf_out.dr;
    mbuf_in.data = '0;

    case (ebuf_out.opcode)
        OP_ADD, OP_NAND, OP_ADDI, OP_JALR,
        OP_LEA, OP_MIN, OP_MAX: begin
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
