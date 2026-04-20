module ras (
    input  logic clk,
    input  logic rst,

    input logic recover,

    // Push Interface (from Decode Stage)
    input  logic push,
    input  logic [31:0] push_data,

    // Pop Interface (from Fetch Stage)
    input  logic pop,
    output logic [31:0] pop_data
);

logic [3:0] rsp;
logic [3:0] next_rsp;
logic [31:0] ras_q [15:0];

// 1. Circular Stack Pointer Logic
always_comb begin
    next_rsp = rsp;
    if (recover || (push && !pop)) begin
        next_rsp = rsp + 4'd1;
    end else if (pop && !push) begin
        next_rsp = rsp - 4'd1;
    end
    // If both push and pop happen, SP stays the same
end

always_ff @(posedge clk) begin
    if (rst) rsp <= 4'd0;
    else     rsp <= next_rsp;
end

// 2. Read Port (Pop) - Native 16-to-1 MUX
logic [3:0] read_idx;
assign read_idx = rsp - 4'd1; // Top of stack is always at SP - 1

cs_mux_16to1 read_mux (
    .d0(ras_q[0]),   .d1(ras_q[1]),   .d2(ras_q[2]),   .d3(ras_q[3]),
    .d4(ras_q[4]),   .d5(ras_q[5]),   .d6(ras_q[6]),   .d7(ras_q[7]),
    .d8(ras_q[8]),   .d9(ras_q[9]),   .d10(ras_q[10]), .d11(ras_q[11]),
    .d12(ras_q[12]), .d13(ras_q[13]), .d14(ras_q[14]), .d15(ras_q[15]),
    .sel(read_idx),
    .y(pop_data)
);

// 3. Write Port (Push)
logic [3:0] write_idx;
// If pushing AND popping simultaneously, the new item overwrites the old top of stack
assign write_idx = (push && pop) ? (rsp - 4'd1) : rsp;

logic [15:0] write_decode;
assign write_decode = push ? (16'd1 << write_idx) : 16'd0;

genvar i;
generate
    for (i = 0; i < 16; i++) begin : RAS_REGS
        cs_register ras_reg (
            .clk(clk),
            .clr(rst),
            .en(write_decode[i]),
            .d(push_data),
            .q(ras_q[i])
        );
    end
endgenerate

endmodule
