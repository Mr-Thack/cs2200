module log(
    input logic [31:0] in,
    input logic cmp,
    input logic_operation op, 
    input logic [31:0] pc,
    input logic [31:0] offset,
    output logic [31:0] out,
    output logic branch_true,
    output logic [31:0] branch_target_line
);

always_comb begin 
    out = '0;
    branch_true = '0;
    branch_target_line = 'X;

    unique case(op)
        LOGIC_JMP_OFFSET: begin
            if (cmp) begin
                branch_true = '1;
                branch_target_line = pc + offset;  
            end
        end

        LOGIC_JMP_RES: begin
            branch_true = '1;
            branch_target_line = in;
            out = pc; // Return address for JALR...
            // I guess this works. But maybe not modular enough.
        end

        LOGIC_IGNORE: begin
            out = in;
        end
    endcase
end

endmodule
