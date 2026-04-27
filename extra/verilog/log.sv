module log(
    input logic [31:0] in,
    input logic cmp,
    input logic predicted_taken,
    input logic_operation op, 
    input logic [31:0] pc,
    input logic [31:0] offset,
    output logic branch_taken,
    output logic [31:0] branch_target
);

always_comb begin 
    branch_taken = '0;
    branch_target = 'X;

    if (op == LOGIC_JMP_OFFSET) begin
        // This is just an alias for cmp since I'm too retarded
        logic actually_taken = cmp;

        // If there's a mismatch between our prediction and reality
        if (actually_taken != predicted_taken) begin
            // FLUSH Pipeline and undo mistake
            branch_taken = '1;

            // But now where do we go?
            if (actually_taken) begin
                // We predicted not taken but it was actually taken
                // So take it now
                branch_target = $signed(pc + $signed(offset));  
            end else begin
                // We predicted taken, but it wasn't actually taken
                // So... we just computed a bunch of trash in IF and DEC
                // So... flush and go back to the original address
                branch_target = pc;
            end
        end
    end
end

endmodule
