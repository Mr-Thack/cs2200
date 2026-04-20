// A single, unified 32-bit entry perfectly sized for our blackboxes
typedef struct packed {
    logic [1:0]  padding; // 2 bits  (Unused, pads to exactly 32 bits)
    logic        valid;   // 1 bit
    logic [10:0] tag;     // 11 bits (PC[15:5]) 
    logic [1:0]  mode;    // 2 bits  (Saturating counter)
    logic [15:0] target;  // 16 bits (Branch Target)
} btb_entry_t; 

module btb (
    input  logic clk,
    input  logic rst,

    // READ PORT (Fetch Stage)
    input  logic [15:0]  read_pc,
    output btb_read_data rdata, 

    // WRITE PORT (Execute Stage)
    input  btb_write_data wdata
);

// 32 discrete register outputs
logic [31:0] btb_q [31:0];

// ==========================================
// READ PORT: 32-to-1 Combinational Read
// ==========================================
logic [4:0]  read_idx; 
logic [10:0] read_tag; 

// Word-addressable: Index starts directly at bit 0
assign read_idx = read_pc[4:0]; 
assign read_tag = read_pc[15:5]; 

logic [31:0] active_entry_raw;
btb_entry_t  active_entry;

// Cast the 32-bit raw output back to our struct
assign active_entry = active_entry_raw;

// The Native 32-to-1 Read MUX
cs_mux_32to1 read_mux (
    .d0(btb_q[0]),   .d1(btb_q[1]),   .d2(btb_q[2]),   .d3(btb_q[3]),
    .d4(btb_q[4]),   .d5(btb_q[5]),   .d6(btb_q[6]),   .d7(btb_q[7]),
    .d8(btb_q[8]),   .d9(btb_q[9]),   .d10(btb_q[10]), .d11(btb_q[11]),
    .d12(btb_q[12]), .d13(btb_q[13]), .d14(btb_q[14]), .d15(btb_q[15]),
    .d16(btb_q[16]), .d17(btb_q[17]), .d18(btb_q[18]), .d19(btb_q[19]),
    .d20(btb_q[20]), .d21(btb_q[21]), .d22(btb_q[22]), .d23(btb_q[23]),
    .d24(btb_q[24]), .d25(btb_q[25]), .d26(btb_q[26]), .d27(btb_q[27]),
    .d28(btb_q[28]), .d29(btb_q[29]), .d30(btb_q[30]), .d31(btb_q[31]),
    .sel(read_idx), 
    .y(active_entry_raw)
);

always_comb begin
    rdata.valid  = 1'b0;
    rdata.take   = 1'b0;
    rdata.target = 16'd0; // 16-bit target

    if (active_entry.valid && active_entry.tag == read_tag) begin
        rdata.valid  = 1'b1;
        rdata.target = active_entry.target;
        rdata.take   = (active_entry.mode >= 2'b10); 
    end
end

// ==========================================
// WRITE PORT: Calculate Next State
// ==========================================
logic [4:0]  up_idx; 
logic [10:0] up_tag; 

assign up_idx = wdata.pc[4:0];
assign up_tag = wdata.pc[15:5];

logic [31:0] current_entry_raw;
btb_entry_t  current_entry;
btb_entry_t  next_entry;

assign current_entry = current_entry_raw;

// The Native 32-to-1 Write MUX (To read the current entry being updated)
cs_mux_32to1 write_mux (
    .d0(btb_q[0]),   .d1(btb_q[1]),   .d2(btb_q[2]),   .d3(btb_q[3]),
    .d4(btb_q[4]),   .d5(btb_q[5]),   .d6(btb_q[6]),   .d7(btb_q[7]),
    .d8(btb_q[8]),   .d9(btb_q[9]),   .d10(btb_q[10]), .d11(btb_q[11]),
    .d12(btb_q[12]), .d13(btb_q[13]), .d14(btb_q[14]), .d15(btb_q[15]),
    .d16(btb_q[16]), .d17(btb_q[17]), .d18(btb_q[18]), .d19(btb_q[19]),
    .d20(btb_q[20]), .d21(btb_q[21]), .d22(btb_q[22]), .d23(btb_q[23]),
    .d24(btb_q[24]), .d25(btb_q[25]), .d26(btb_q[26]), .d27(btb_q[27]),
    .d28(btb_q[28]), .d29(btb_q[29]), .d30(btb_q[30]), .d31(btb_q[31]),
    .sel(up_idx), 
    .y(current_entry_raw)
);

always_comb begin
    // Default: keep exactly what's there
    next_entry = current_entry;

    if (current_entry.valid && current_entry.tag == up_tag) begin
        // Hit: Update the saturating counter
        if (wdata.taken && current_entry.mode < 2'b11) begin 
            next_entry.mode = current_entry.mode + 2'd1;
        end else if (!wdata.taken && current_entry.mode > 2'b00) begin 
            next_entry.mode = current_entry.mode - 2'd1;
        end
        next_entry.target = wdata.target;
    end else begin
        // Miss: Evict and allocate 
        next_entry.padding = 2'b00; // Updated padding to 2 bits
        next_entry.valid   = 1'b1;
        next_entry.tag     = up_tag;
        next_entry.mode    = wdata.taken ? 2'b10 : 2'b01; 
        next_entry.target  = wdata.target; 
    end
end

// ==========================================
// WRITE PORT EXECUTION: The Generate Loop
// ==========================================
logic [31:0] write_decode;

// Drive exactly 1 line of the 32-bit bus high if we are writing
assign write_decode = wdata.write ? (32'd1 << up_idx) : 32'd0;

logic [31:0] next_entry_raw;
assign next_entry_raw = next_entry; // Cast for the blackbox

genvar i;
generate
    // Unroll 32 discrete physical registers
    for (i = 0; i < 32; i++) begin : BTB_REGS
        cs_register btb_reg (
            .clk(clk),
            .clr(rst),
            .en(write_decode[i]),
            .d(next_entry_raw),
            .q(btb_q[i])
        );
    end
endgenerate

endmodule
