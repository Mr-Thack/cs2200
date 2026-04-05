module dprf(
    input logic clk,
    input logic rst,
    input logic we,
    input logic [3:0] regno_read1,
    input logic [3:0] regno_read2,
    input logic [3:0] regno_write,
    input logic [31:0] write_data,
    output logic [31:0] read_data1,
    output logic [31:0] read_data2
);
    localparam NUM_REG = 16;

    // 16 registers, each 32 bits
    (* ram_style = "logic" *) logic [31:0] registers [NUM_REG];

    always_ff @(posedge clk) begin
        if (we && regno_write != 4'd0) begin
            // If Write_Enable and not $zero, write
            registers[regno_write] <= write_data;
        end
    end

    // A long time ago, these two lines below were a nice pretty function
    // BUT, the stupid retarded Yosys was incapable of understanding
    // that this is just a fancy mux.
    // That's ok I guess. But, now we've got this ugly ternary operator

    // Read Port 1
    assign read_data1 = (regno_read1 == 4'd0) ? 32'd0 :
                        (we && (regno_write == regno_read1)) ? write_data :
                        registers[regno_read1];

    // Read Port 2
    assign read_data2 = (regno_read2 == 4'd0) ? 32'd0 :
                        (we && (regno_write == regno_read2)) ? write_data :
                        registers[regno_read2];

endmodule
