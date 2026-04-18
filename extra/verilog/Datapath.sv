// --- MAGIC BLACKBOXES ---
// These tell Yosys "trust me, these exist in hardware" so it doesn't crash.

(* blackbox *)
module cs_clock (output logic clk);
endmodule

(* blackbox *)
module cs_probe #(parameter WIDTH = 1) (input logic [WIDTH-1:0] val);
endmodule

// --- TOP LEVEL FOR AUTOGRADER ---
(* keep_hierarchy = "true" *)
module Datapath();

logic clk;
logic rst;

// 1. Generate the Clock Peer
(* keep *) cs_clock clock_gen (
    .clk(clk)
);

// 2. Hardcode Reset to 0
assign rst = 1'b0;

// (* keep *) logic [31:0] debug_pc;
// (* keep *) logic halt;
// (* keep *) logic [31:0] cycles;

// 3. Instantiate CPU
(* keep *) pipeline dut (
    .clk(clk),
    .rst(rst)
);

// 4. Drop probes to prevent Yosys from optimizing the pipeline away
// (* keep *) cs_probe #(.WIDTH(32)) probe_pc (.val(debug_pc));
// (* keep *) cs_probe #(.WIDTH(1)) probe_halt (.val(halt));
// (* keep *) cs_probe #(.WIDTH(32)) probe_cycles (.val(cycles));

endmodule
