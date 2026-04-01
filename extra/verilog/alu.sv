import types::*;

module alu(
    input logic [31:0] a,
    input logic [31:0] b,
    input operation op,
    output logic [31:0] out
);
    always_comb begin 
        case(op)
            ADD: out = $signed($signed(a) + $signed(b));
            SUB: out = $signed($signed(a) - $signed(b));
            NAND: out = ~(a & b);
            ADD1: out = a + 1;
            PASSA: out = a;
            PASSB: out = b;
            IGNORE: out = 'X;
            default: out = 'X;
            // Triggers error if non-defined code 
        endcase
    end

endmodule
