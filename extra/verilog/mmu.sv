module mmu (
    input logic clk,
    input logic rst,

    input logic [15:0] PC,
    input logic [31:0] mem_out,

    // Only inst0 is guaranteed valid
    output logic [31:0] inst1,
    output logic [31:0] inst2,
    output logic [31:0] inst3,

    // 2-bit wire encoding 0, 1, 2, or 3 extra valid instructions
    output logic [1:0] extra_valid 
);

// ==========================================
// BANK INTERCONNECTS
// ==========================================
logic [31:0] bank_dout [4];
logic bank_valid [4];

// Literal instantiations to bypass CircuitSim parameter limitations
bank bank0 (.clk(clk), .rst(rst), .bank_index(2'd0), .addr(PC), .din(mem_out), .dout(bank_dout[0]), .is_valid(bank_valid[0]));
bank bank1 (.clk(clk), .rst(rst), .bank_index(2'd1), .addr(PC), .din(mem_out), .dout(bank_dout[1]), .is_valid(bank_valid[1]));
bank bank2 (.clk(clk), .rst(rst), .bank_index(2'd2), .addr(PC), .din(mem_out), .dout(bank_dout[2]), .is_valid(bank_valid[2]));
bank bank3 (.clk(clk), .rst(rst), .bank_index(2'd3), .addr(PC), .din(mem_out), .dout(bank_dout[3]), .is_valid(bank_valid[3]));

// ==========================================
// ASSEMBLE OUTPUT BUNDLE
// ==========================================
logic [1:0] id1, id2, id3;
assign id1 = 2'(PC + 16'd1);
assign id2 = 2'(PC + 16'd2);
assign id3 = 2'(PC + 16'd3);

assign inst1 = bank_dout[id1];
assign inst2 = bank_dout[id2];
assign inst3 = bank_dout[id3];

// Check validity cascade
logic v1, v2, v3;
assign v1 = bank_valid[id1];
assign v2 = bank_valid[id2];
assign v3 = bank_valid[id3];

always_comb begin
    if      (v1 && v2 && v3) extra_valid = 2'd3;
    else if (v1 && v2)       extra_valid = 2'd2;
    else if (v1)             extra_valid = 2'd1;
    else                     extra_valid = 2'd0;
end

endmodule
