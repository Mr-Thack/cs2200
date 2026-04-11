module alu(
    input logic [31:0] a,
    input logic [31:0] b,
    input alu_operation op,
    output logic [31:0] out
);
    always_comb begin 
        unique case(op)
            ALU_ADD: out = $signed($signed(a) + $signed(b));
            ALU_SUB: out = $signed($signed(a) - $signed(b));
            ALU_NAND: out = ~(a & b);
            ALU_ADD1: out = a + 1;
            ALU_PASSA: out = a;
            ALU_PASSB: out = b; 
            ALU_IGNORE: out = 'X;
            // Triggers error if non-defined code 
        endcase
    end

endmodule
