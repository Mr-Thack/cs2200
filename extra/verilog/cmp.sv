module cmp(
    input logic [31:0] in,
    input cmp_operation op,
    output logic out
);

always_comb begin 
    unique case(op)
        CMP_LT: out = $signed(in) < 0;
        CMP_EQ: out = $signed(in) == 0;
        CMP_GT: out = $signed(in) > 0;
        CMP_IGNORE: out = '0;
    endcase
end

endmodule
