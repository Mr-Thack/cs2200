module bank (
    input logic clk,
    input logic rst,

    input logic [1:0] bank_index,

    input logic [15:0] addr,

    input logic [31:0] din,
    output logic [31:0] dout,

    output logic is_valid,
    input logic is_write
);

// 16384 words per bank
(* nomem2reg *) logic [31:0] ram [16384];

logic [13:0] index;
assign index = addr[15:2];

logic [31:0] read_data;
assign read_data = is_write ? '0 : ram[index];

always_comb begin
    if (is_write) begin
        // We are busy writing the snooped value!
        dout = '0;
        is_valid = 1'b0;
    end else begin 
        dout = read_data;
        is_valid = (dout == '0) ? '0 : '1;
    end
end

// ----------------------------------------------------
// 3. Write Logic (Sequential)
// ----------------------------------------------------
always_ff @(posedge clk) begin
    if (is_write) begin
        // ALWAYS write to ourselves if the base PC is in our jurisdiction
        ram[index] <= din;
    end
end

endmodule
