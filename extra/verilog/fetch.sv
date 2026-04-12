module fetch(
    input logic clk,
    input logic rst,

    input logic [31:0] PC,
    input instruction_data IR,

    output predict_taken,
    output logic [31:0] predict_target,

    input btb_read_data rdata,

    output fbuf_data fbuf
);


logic [31:0] ext_imm;
assign ext_imm = {{12{IR.imm[19]}}, IR.imm};

always_comb begin
    fbuf.instruction = IR;
    fbuf.pc_plus_1 = PC + 1;

    predict_taken = '0;
    predict_target = 'X;

    if (IR.opcode inside {OP_BEQ, OP_BGT}) begin
        if (rdata.valid) begin
            predict_taken = rdata.take;
            predict_target = rdata.target; 
        end else begin
            if ($signed(ext_imm) < 0) begin 
                predict_taken = '1;
                // The ISA treats branch offset as starting from PC + 1
                predict_target = $signed(fbuf.pc_plus_1 + $signed(ext_imm));
            end
        end
    end

    fbuf.predicted_taken = predict_taken;
    fbuf.btb_hit = rdata.valid;
    fbuf.valid = '1;
end

endmodule
