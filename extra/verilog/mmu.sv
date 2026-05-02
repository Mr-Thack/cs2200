module mmu (
    input logic clk,
    input logic rst,

    input logic [15:0] PC,
    output logic [15:0] imem_addr,
    input logic [31:0] mem_out,

    output logic [31:0] inst0,
    output logic [31:0] inst1,
    output logic [31:0] inst2,
    output logic [31:0] inst3,

    // 2-bit wire encoding 0, 1, 2, or 3 extra valid instructions
    output logic [1:0] extra_valid 
);

// ==========================================
// STALL DETECTION & ADDRESS CALCULATION
// ==========================================
logic [15:0] last_PC;
logic last_PC_valid;

always_ff @(posedge clk) begin
    if (rst) begin
        // Use an unlikely PC reset value to prevent a false 
        // match on the very first cycle after reset
        last_PC <= 16'd0; 
        last_PC_valid <= 1'b0;
    end else begin
        last_PC <= PC;
        last_PC_valid <= 1'b1;
    end
end

// If PC hasn't changed, feed PC+1 to the banks so it captures the new data
assign imem_addr = (last_PC_valid && PC == last_PC) ? (PC + 16'd1) : PC;

// ==========================================
// INDEPENDENT BANK ADDRESS CALCULATION
// ==========================================
logic [15:0] bank_addr [4];
logic bank_we [4];

always_comb begin
    for (int i = 0; i < 4; i++) begin
        // Are we writing to this bank? (Snooping main memory)
        bank_we[i] = (imem_addr[1:0] == 2'(i));

        if (bank_we[i]) begin
            // If writing, use the global imem_addr so it goes to the right block
            bank_addr[i] = imem_addr;
        end else begin
            // If reading, use the Wrap-Around Trick!
            // If this bank's ID is less than the current PC's offset, it has wrapped into the next block.
            if (2'(i) < PC[1:0]) begin
                bank_addr[i] = { (PC[15:2] + 14'd1), 2'(i) }; 
            end else begin
                bank_addr[i] = { PC[15:2], 2'(i) };
            end
        end
    end
end

// ==========================================
// BANK INTERCONNECTS
// ==========================================
logic [31:0] bank_dout [4];
logic bank_valid [4];

// Literal instantiations to bypass CircuitSim parameter limitations
bank bank0 (.clk(clk), .rst(rst), .bank_index(2'd0), .addr(bank_addr[0]), .is_write(bank_we[0]), .din(mem_out), .dout(bank_dout[0]), .is_valid(bank_valid[0]));
bank bank1 (.clk(clk), .rst(rst), .bank_index(2'd1), .addr(bank_addr[1]), .is_write(bank_we[1]), .din(mem_out), .dout(bank_dout[1]), .is_valid(bank_valid[1]));
bank bank2 (.clk(clk), .rst(rst), .bank_index(2'd2), .addr(bank_addr[2]), .is_write(bank_we[2]), .din(mem_out), .dout(bank_dout[2]), .is_valid(bank_valid[2]));
bank bank3 (.clk(clk), .rst(rst), .bank_index(2'd3), .addr(bank_addr[3]), .is_write(bank_we[3]), .din(mem_out), .dout(bank_dout[3]), .is_valid(bank_valid[3]));

// ==========================================
// ASSEMBLE OUTPUT BUNDLE
// ==========================================
logic [1:0] id0, id1, id2, id3;
assign id0 = 2'(PC);
assign id1 = 2'(PC + 16'd1);
assign id2 = 2'(PC + 16'd2);
assign id3 = 2'(PC + 16'd3);

logic [1:0] write_id;
assign write_id = imem_addr[1:0];

// BYPASS NETWORK: If the bank we want is currently being written to, 
// its output is 0. Instead, grab the data directly off the mem_out bus!
assign inst0 = (id0 == write_id) ? mem_out : bank_dout[id0];
assign inst1 = (id1 == write_id) ? mem_out : bank_dout[id1];
assign inst2 = (id2 == write_id) ? mem_out : bank_dout[id2];
assign inst3 = (id3 == write_id) ? mem_out : bank_dout[id3];


// Check validity cascade
logic v1, v2, v3;
assign v1 = (id1 == write_id) ? 1'b1 : bank_valid[id1];
assign v2 = (id2 == write_id) ? 1'b1 : bank_valid[id2];
assign v3 = (id3 == write_id) ? 1'b1 : bank_valid[id3];

always_comb begin
    if      (v1 && v2 && v3) extra_valid = 2'd3;
    else if (v1 && v2)       extra_valid = 2'd2;
    else if (v1)             extra_valid = 2'd1;
    else                     extra_valid = 2'd0;
end

endmodule
