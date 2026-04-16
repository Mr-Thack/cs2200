// A single, unified 32-bit entry
typedef struct packed {
    logic        valid;  // 1 bit
    logic [12:0]  tag;    // 13 bits (PC[15:3]) [SIZE]
    logic [1:0]  mode;   // 2 bits  (Saturating counter)
    logic [15:0] target; // 16 bits (Branch Target)
} btb_entry_t; 

module btb (
    input  logic clk,
    input  logic rst,

    // READ PORT (Fetch Stage)
    input  logic [31:0]  read_pc,
    output btb_read_data rdata, 

    // WRITE PORT (Execute Stage)
    input  btb_write_data wdata
);

// [SIZE]
// Our single array of 8 discrete size(btb_entry_t) registers
btb_entry_t btb_array [8]; 

// ==========================================
// READ PORT: Combinational Read
// ==========================================
logic [2:0] read_idx; // [SIZE]
logic [12:0] read_tag; // [SIZE]

assign read_idx = read_pc[2:0]; // [SIZE]
assign read_tag = read_pc[15:3]; // [SIZE]

btb_entry_t active_entry;
assign active_entry = btb_array[read_idx];

always_comb begin
    rdata.valid  = 1'b0;
    rdata.take   = 1'b0;
    rdata.target = 32'd0;

    if (active_entry.valid && active_entry.tag == read_tag) begin
        rdata.valid  = 1'b1;
        // Pad the 16-bit stored target back to 32 bits at zero cost
        rdata.target = {16'd0, active_entry.target};
        rdata.take   = (active_entry.mode >= 2'b10); 
    end
end

// ==========================================
// WRITE PORT: Calculate Next State
// ==========================================
logic [2:0] up_idx; // [SIZE]
logic [12:0] up_tag; // [SIZE]

assign up_idx = wdata.pc[2:0];
assign up_tag = wdata.pc[15:3];

btb_entry_t current_entry;
btb_entry_t next_entry;

assign current_entry = btb_array[up_idx];

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
        // Refresh the target just in case, though it shouldn't normally change on a hit
        next_entry.target = wdata.target[15:0];
    end else begin
        // Miss: Evict and allocate 
        next_entry.valid  = 1'b1;
        next_entry.tag    = up_tag;
        next_entry.mode   = wdata.taken ? 2'b10 : 2'b01; 
        next_entry.target = wdata.target[15:0]; // Slice the bottom 16 bits
    end
end

// ==========================================
// WRITE PORT EXECUTION: The Generate Loop
// ==========================================

// [SIZE]
logic [7:0] write_decode;
// Forcing this into a MUX instead of a bunch of MUX's and Splitter's
// [SIZE]
assign write_decode = wdata.write ? (8'd1 << up_idx) : '0;

genvar i;
generate
// [SIZE]
for (i = 0; i < 8; i++) begin : BTB_REGS
    always_ff @(posedge clk) begin
        if (rst) begin
            // Only clear the valid bit to save routing overhead on reset
            btb_array[i]  <= '0;
        end else if (write_decode[i]) begin
            // Single, clean assignment
            btb_array[i] <= next_entry;
        end
    end
end
endgenerate

endmodule
