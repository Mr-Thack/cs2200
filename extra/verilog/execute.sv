module execute(
    input dbuf_data dbuf,
    input logic [31:0] fwd_val1,
    input logic [31:0] fwd_val2,

    output logic branch_true,
    output logic [31:0] branch_target_line,
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
    .op(dbuf.logop),
    .pc(dbuf.pc_plus_1),
    .offset(dbuf.offset),
    .out(log_result),
    .branch_true(branch_true),
    .branch_target_line(branch_target_line)
);

always_comb begin
    ebuf.dr = dbuf.dr;
    ebuf.memop = dbuf.memop;
    ebuf.address = (dbuf.memop != MEM_IGNORE) ? log_result : '0;
    // We're just gonna hardcore source_val1 as the stuff to write since
    // I don't care...
    ebuf.data = (dbuf.memop == MEM_WRITE) ? fwd_val1 : log_result;
end

endmodule
