// dprf.sv
module dprf(
    input  logic clk,
    input  logic rst,
    input  logic we,
    input  logic [3:0]  regno_read1,
    input  logic [3:0]  regno_read2,
    input  logic [3:0]  regno_write,
    input  logic [31:0] write_data,
    output logic [31:0] read_data1,
    output logic [31:0] read_data2
);

// --- Write Enable Decoder ---
logic [15:0] we_dec;
always_comb begin
    we_dec = 16'd0;
    if (we) begin
        // Explicit left shift since Yosys will go spawn a $shift component
        // That uses signed shift selection but CircuitSim only supports
        // Unsigned and I don't feel like messing with the compiler anymore
        we_dec = 1'b1 << regno_write;
    end
end

// --- Register Output Wires ---
logic [31:0] reg_out_0, reg_out_1, reg_out_2, reg_out_3;
logic [31:0] reg_out_4, reg_out_5, reg_out_6, reg_out_7;
logic [31:0] reg_out_8, reg_out_9, reg_out_10, reg_out_11;
logic [31:0] reg_out_12, reg_out_13, reg_out_14, reg_out_15;

// --- Explicit Blackbox Register Instances ---
// $zero gets a hardwired 0 enable. Yosys cannot optimize this away!
cs_register reg_zero (.clk(1'b0), .clr(rst), .en(1'b0),       .d(write_data), .q(reg_out_0));
cs_register reg_at   (.clk(clk), .clr(rst), .en(we_dec[1]),  .d(write_data), .q(reg_out_1));
cs_register reg_v0   (.clk(clk), .clr(rst), .en(we_dec[2]),  .d(write_data), .q(reg_out_2));
cs_register reg_a0   (.clk(clk), .clr(rst), .en(we_dec[3]),  .d(write_data), .q(reg_out_3));
cs_register reg_a1   (.clk(clk), .clr(rst), .en(we_dec[4]),  .d(write_data), .q(reg_out_4));
cs_register reg_a2   (.clk(clk), .clr(rst), .en(we_dec[5]),  .d(write_data), .q(reg_out_5));
cs_register reg_t0   (.clk(clk), .clr(rst), .en(we_dec[6]),  .d(write_data), .q(reg_out_6));
cs_register reg_t1   (.clk(clk), .clr(rst), .en(we_dec[7]),  .d(write_data), .q(reg_out_7));
cs_register reg_t2   (.clk(clk), .clr(rst), .en(we_dec[8]),  .d(write_data), .q(reg_out_8));
cs_register reg_s0   (.clk(clk), .clr(rst), .en(we_dec[9]),  .d(write_data), .q(reg_out_9));
cs_register reg_s1   (.clk(clk), .clr(rst), .en(we_dec[10]), .d(write_data), .q(reg_out_10));
cs_register reg_s2   (.clk(clk), .clr(rst), .en(we_dec[11]), .d(write_data), .q(reg_out_11));
cs_register reg_k0   (.clk(clk), .clr(rst), .en(we_dec[12]), .d(write_data), .q(reg_out_12));
cs_register reg_sp   (.clk(clk), .clr(rst), .en(we_dec[13]), .d(write_data), .q(reg_out_13));
cs_register reg_fp   (.clk(clk), .clr(rst), .en(we_dec[14]), .d(write_data), .q(reg_out_14));
cs_register reg_ra   (.clk(clk), .clr(rst), .en(we_dec[15]), .d(write_data), .q(reg_out_15));

// --- Explicit Blackbox Muxes ---
logic [31:0] raw_read1, raw_read2;

cs_mux_16to1 read1_mux (
    .d0(reg_out_0),   .d1(reg_out_1),   .d2(reg_out_2),   .d3(reg_out_3),
    .d4(reg_out_4),   .d5(reg_out_5),   .d6(reg_out_6),   .d7(reg_out_7),
    .d8(reg_out_8),   .d9(reg_out_9),   .d10(reg_out_10), .d11(reg_out_11),
    .d12(reg_out_12), .d13(reg_out_13), .d14(reg_out_14), .d15(reg_out_15),
    .sel(regno_read1), .y(raw_read1)
);

cs_mux_16to1 read2_mux (
    .d0(reg_out_0),   .d1(reg_out_1),   .d2(reg_out_2),   .d3(reg_out_3),
    .d4(reg_out_4),   .d5(reg_out_5),   .d6(reg_out_6),  .d7(reg_out_7),
    .d8(reg_out_8),   .d9(reg_out_9),   .d10(reg_out_10), .d11(reg_out_11),
    .d12(reg_out_12), .d13(reg_out_13), .d14(reg_out_14), .d15(reg_out_15),
    .sel(regno_read2), .y(raw_read2)
);

// --- Bypass Routing ---
assign read_data1 = (we && (regno_write == regno_read1) && (regno_read1 != 4'd0)) ? write_data : raw_read1;
assign read_data2 = (we && (regno_write == regno_read2) && (regno_read2 != 4'd0)) ? write_data : raw_read2;

endmodule
