module execute(
    input dbuf_data dbuf,
    input logic [31:0] fwd_val1,
    input logic [31:0] fwd_val2,

    output logic branch_taken,
    output logic [31:0] branch_target,
    output btb_write_data wdata,
    output ebuf_data ebuf
);

logic [31:0] alu_val1;
logic [31:0] alu_val2;
logic [31:0] alu_result;
logic cmp_result;

always_comb begin
    unique case(dbuf.src1)
       ALU_VAL1:    alu_val1 = fwd_val1; 
       ALU_VAL2:    alu_val1 = fwd_val2; 
       ALU_OFFSET:  alu_val1 = dbuf.offset; 
       ALU_PC:      alu_val1 = dbuf.pc_plus_1; 
    endcase
    
    unique case(dbuf.src2)
        ALU_VAL1:    alu_val2 = fwd_val1; 
        ALU_VAL2:    alu_val2 = fwd_val2; 
        ALU_OFFSET:  alu_val2 = dbuf.offset; 
        ALU_PC:      alu_val2 = dbuf.pc_plus_1; 
    endcase
end


alu alu0 (
    .a(alu_val1),
    .b(alu_val2),
    .op(dbuf.aluop),
    .out(alu_result)
);

cmp cmp0 (
    .in(alu_result),
    .op(dbuf.cmpop),
    .out(cmp_result)
);

log log0 (
    .in(alu_result),
    .cmp(cmp_result),
    .predicted_taken(dbuf.predicted_taken),
    .op(dbuf.logop),
    .pc(dbuf.pc_plus_1),
    .offset(dbuf.offset),
    .branch_taken(branch_taken),
    .branch_target(branch_target)
);

always_comb begin
    ebuf.dr = dbuf.dr;
    ebuf.memop = dbuf.memop;
    ebuf.address = (dbuf.memop != MEM_IGNORE) ? alu_result : '0;
    ebuf.mem_data = fwd_val1;
    ebuf.reg_data = alu_result;
    ebuf.valid = dbuf.valid;
    ebuf.instructions_merged = dbuf.instructions_merged;

    // Initialize to 0 because split_wide will split this into multiple
    // registers
    wdata.pc = '0;
    wdata.target = '0;
    wdata.taken = '0;
    wdata.write = '0;

    if (dbuf.logop == LOGIC_JMP_OFFSET) begin
        // Only populate BTB with non-trivial JMPs
        // since trivial ones are now evaluated in Fetch and Decode
        if (dbuf.sr1 != dbuf.sr2) begin
            wdata.pc = dbuf.pc_plus_1 - 32'd1;
            wdata.target = $signed(dbuf.pc_plus_1 + $signed(dbuf.offset));
            wdata.taken = cmp_result;
            wdata.write = '1;
        end
    end

    if (dbuf.logop == LOGIC_JMP_RES) begin
        // Populate BTB for JALR calls (since they could be offsets
        // and we just don't know
        //
        // Also, even though we're resolving JALR's in Decode,
        // the reason why this is here is because we only have 1 write port
        // to the BTB
        if (dbuf.dr != 4'd0) begin
            wdata.pc = dbuf.pc_plus_1 - 32'd1;
            wdata.target = fwd_val1;
            wdata.taken = 1'b1;
            wdata.write = 1'b1;
        end
    end
end

endmodule
