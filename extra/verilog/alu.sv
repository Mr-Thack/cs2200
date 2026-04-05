module alu(
    input logic [31:0] a,
    input logic [31:0] b,
    input types::alu_operation op,
    output logic [31:0] out
);
    always_comb begin 
        case(op)
            types::ALU_ADD: out = $signed($signed(a) + $signed(b));
            types::ALU_SUB: out = $signed($signed(a) - $signed(b));
            types::ALU_NAND: out = ~(a & b);
            types::ALU_ADD1: out = a + 1;
            types::ALU_PASSA: out = a;
            types::ALU_PASSB: out = b;
            types::ALU_IGNORE: out = 'X;
            default: out = 'X;
            // Triggers error if non-defined code 
        endcase
    end

endmodule
