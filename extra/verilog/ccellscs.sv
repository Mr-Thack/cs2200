(* blackbox *)
module cs_register (
    input  logic clk,
    input  logic clr,
    input  logic en,
    input  logic [31:0] d,
    output logic [31:0] q
);
endmodule

(* blackbox *)
module cs_mux_16to1 (
    input logic [31:0] d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12, d13, d14, d15,
    input logic [3:0] sel, output logic [31:0] y);
endmodule

(* blackbox *)
module cs_mux_32to1 (
    input logic [31:0] d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12, d13, d14, d15,
    input logic [31:0] d16, d17, d18, d19, d20, d21, d22, d23, d24, d25, d26, d27, d28, d29, d30, d31,
    input logic [4:0] sel,
    output logic [31:0] y);
endmodule
