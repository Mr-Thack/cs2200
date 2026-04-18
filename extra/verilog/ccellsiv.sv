module cs_register (
    input  logic clk,
    input  logic clr,
    input  logic en,
    input  logic [31:0] d,
    output logic [31:0] q
);
    // Asynchronous clear, synchronous enable (matches CircuitSim default)
    always_ff @(posedge clk or posedge clr) begin
        if (clr) begin
            q <= 32'd0;
        end else if (en) begin
            q <= d;
        end
    end
endmodule

module cs_mux_16to1 (
    input logic [31:0] d0, d1, d2, d3, d4, d5, d6, d7, 
    d8, d9, d10, d11, d12, d13, d14, d15,
    input logic [3:0] sel,
    output logic [31:0] y
);
    logic [31:0] inputs [15:0];
    assign inputs[0]  = d0;  assign inputs[1]  = d1;
    assign inputs[2]  = d2;  assign inputs[3]  = d3;
    assign inputs[4]  = d4;  assign inputs[5]  = d5;
    assign inputs[6]  = d6;  assign inputs[7]  = d7;
    assign inputs[8]  = d8;  assign inputs[9]  = d9;
    assign inputs[10] = d10; assign inputs[11] = d11;
    assign inputs[12] = d12; assign inputs[13] = d13;
    assign inputs[14] = d14; assign inputs[15] = d15;
    assign y = inputs[sel];
endmodule


module cs_mux_32to1 (
    input logic [31:0] d0, d1, d2, d3, d4, d5, d6, d7, 
    d8, d9, d10, d11, d12, d13, d14, d15,
    d16, d17, d18, d19, d20, d21, d22, d23,
    d24, d25, d26, d27, d28, d29, d30, d31,
    input logic [4:0] sel,
    output logic [31:0] y
);
    logic [31:0] inputs [31:0];
    assign inputs[0]  = d0;  assign inputs[1]  = d1;
    assign inputs[2]  = d2;  assign inputs[3]  = d3;
    assign inputs[4]  = d4;  assign inputs[5]  = d5;
    assign inputs[6]  = d6;  assign inputs[7]  = d7;
    assign inputs[8]  = d8;  assign inputs[9]  = d9;
    assign inputs[10] = d10; assign inputs[11] = d11;
    assign inputs[12] = d12; assign inputs[13] = d13;
    assign inputs[14] = d14; assign inputs[15] = d15;
    assign inputs[16]  = d16;  assign inputs[17]  = d17;
    assign inputs[18]  = d18;  assign inputs[19]  = d19;
    assign inputs[20]  = d20;  assign inputs[21]  = d21;
    assign inputs[22]  = d22;  assign inputs[23]  = d23;
    assign inputs[24]  = d24;  assign inputs[25]  = d25;
    assign inputs[26]  = d26;  assign inputs[27]  = d27;
    assign inputs[28]  = d28;  assign inputs[29]  = d29;
    assign inputs[30]  = d30;  assign inputs[31]  = d31;
    assign y = inputs[sel];
endmodule
