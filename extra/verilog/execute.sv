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
logic [31:0] log_result;

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
    .out(log_result),
    .branch_taken(branch_taken),
    .branch_target(branch_target)
);

always_comb begin
    ebuf.dr = dbuf.dr;
    ebuf.memop = dbuf.memop;
    ebuf.address = (dbuf.memop != MEM_IGNORE) ? log_result : '0;
    // We're just gonna hardcore source_val1 as the stuff to write since
    // I don't care...
    ebuf.data = (dbuf.memop == MEM_WRITE) ? fwd_val1 : log_result;
    ebuf.valid = dbuf.valid;

    if (dbuf.logop == LOGIC_JMP_OFFSET) begin
        wdata.pc = dbuf.pc_plus_1 - 32'd1;
        wdata.target = $signed(dbuf.pc_plus_1 + $signed(dbuf.offset));
        wdata.taken = cmp_result;
        wdata.write = '1;
    end else begin
        wdata.pc = '0;
        wdata.target = '0;
        wdata.taken = '0;
        wdata.write = '0;
    end
end

endmodule
