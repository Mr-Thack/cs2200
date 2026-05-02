module fetch(
    input logic clk,
    input logic rst,

    input logic [31:0] PC,
    output logic [15:0] imem_addr,
    input logic [31:0] imem_out,
    
    input logic branch_taken,
    input logic stall_now,

    output predict_taken,
    output logic [31:0] predict_target,

    input btb_read_data rdata,

    output fbuf_data fbuf,

    input logic [31:0] ras_pop_data,

    output logic ras_pop
);

instruction_data IR1, IR2, IR3, IR4;
logic [1:0] extras;

mmu baby_mmu (
    .clk(clk),
    .rst(rst),

    .PC(PC[15:0]),
    .imem_addr(imem_addr),
    .mem_out(imem_out),

    .inst0(IR1),
    .inst1(IR2),
    .inst2(IR3),
    .inst3(IR4),
    
    .extra_valid(extras)
);



logic [31:0] ext_imm;
assign ext_imm = {{12{IR1.imm[19]}}, IR1.imm};

control_word_t cw;

fusion fuse(
    .ins1(IR1),
    .ins2(IR2),
    .extras(extras),
    .cw(cw)
);

always_comb begin
    fbuf.pc_plus_1 = PC + 32'd1;
    fbuf.ins1 = IR1;
    fbuf.ins2 = IR2;
    fbuf.cw = cw;

    ras_pop = 1'b0;
    predict_taken = '0;
    // Safe default. 'X was causing the CPU to crash. Dunno why.
    // Don't have time to care
    // UPDATE:
    // I reverted this back to 'X, but this is important so noting here:
    // So, in decode, we were checking if jalr_target_fwd == fbuf.predict_target
    // But if it's 'X, then we're comparing to null which is undefined
    // But that made me realize that we're only updating our JALR predictions
    // during the EXEC stage. That means that theoretically if you had a 
    // recursive call, you would lose one clock cycle on the first JMP
    // (since we don't know where it goes), but then, we would lose a 2nd
    // on the 2nd jump of a recursive call (since the correct branch predict
    // wouldn't have been saved yet!)
    // Just thought that was interesting to note.
    // We could solve this with a Dual Input BTB, but I just don't care
    // enough.
    predict_target = 'X;

    if (IR1.opcode inside {OP_BEQ, OP_BGT}) begin
        // This is what we do if if the branch is taken
        predict_taken = 1'b1;
        // The ISA treats branch offset as starting from PC + 1
        predict_target = $signed(fbuf.pc_plus_1 + $signed(ext_imm));

        // If not trivially true
        if (IR1.rx != IR1.ry) begin
            if (rdata.valid) begin
                predict_taken = rdata.take;
            end else if ($signed(ext_imm) > 0) begin 
                // Default Policy of Backwards Taken Forwards Not Taken
                predict_taken = 1'b0;
            end
        end
    end
    
    if (IR1.opcode == OP_JALR) begin
        predict_taken = 1'b1;
        if (IR1.ry == 4'd0) begin
            // Pop RAS because this is a return
            predict_target = ras_pop_data;
            ras_pop = !branch_taken && !stall_now;
            // Don't actually pop if we're gonna be flushing
        end else if (rdata.valid) begin
            predict_target = rdata.target;
        end else begin
            predict_taken = 1'b0;
        end 
    end

    fbuf.predicted_taken = predict_taken;
    fbuf.predict_target = predict_target;
    fbuf.btb_hit = rdata.valid;
    fbuf.ras_was_popped = ras_pop;
    fbuf.valid = 1'b1;
end

endmodule
