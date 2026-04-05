module mem #(
    // This fancy hashtag thingy lets me put an INIT file into the mem
    parameter INIT = ""
)(
    input logic clk,
    input logic rst,
    input logic we,
    input logic [15:0] addr,
    input logic [31:0] write_data,
    output logic [31:0] read_data
);
    localparam SIZE = 2**16;

    (* nomem2reg *) logic [31:0] RAM [SIZE];

    // Load from Init ROM, if it exists
    initial begin
        if (INIT != "") begin
            $readmemh(INIT, RAM);
        end
    end

    always_ff @(posedge clk) begin
        if (we) begin
            RAM[addr] <= write_data;
        end
    end

    assign read_data = RAM[addr];

endmodule
