// --- MAGIC BLACKBOXES ---
// These tell Yosys "trust me, these exist in hardware" so it doesn't crash.

(* blackbox *)
module cs_clock (output logic clk);
endmodule

(* blackbox *)
module cs_probe #(parameter WIDTH = 1) (input logic [WIDTH-1:0] val);
endmodule

// --- TOP LEVEL FOR AUTOGRADER ---

module Datapath();

logic clk;
logic rst;

// 1. Generate the Clock Peer
cs_clock clock_gen (
    .clk(clk)
);

// 2. Hardcode Reset to 0
assign rst = 1'b0;

logic [31:0] debug_pc;
logic halt;
logic [31:0] cycles;

// 3. Instantiate CPU
pipeline dut (
    .clk(clk),
    .rst(rst),
    .debug_pc(debug_pc),
    .halt_flag(halt),
    .out_stat_cycles(cycles)
);

// 4. Drop probes to prevent Yosys from optimizing the pipeline away
cs_probe #(.WIDTH(32)) probe_pc (.val(debug_pc));
cs_probe #(.WIDTH(1)) probe_halt (.val(halt));
cs_probe #(.WIDTH(32)) probe_cycles (.val(cycles));

endmodule
