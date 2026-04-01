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
    logic [31:0] registers [NUM_REG];

    always_ff @(posedge clk) begin
        if (rst) begin
            // Clear all registers
            for (int i = 0; i < NUM_REG; i++) begin
                registers[i] <= '0;
            end
        end else if (we && regno_write != 4'd0) begin
            // If Write_Enable and not $zero, write
            registers[regno_write] <= write_data;
        end
    end

    function logic [31:0] read_port(input logic [3:0] regno);
        if (regno == 4'd0) begin
            return '0; // Force to 0 in case of bad initialization
        end else if (we && (regno_write == regno)) begin
            return write_data; // Port Forwarding
        end else begin
            return registers[regno];
        end
    endfunction

    assign read_data1 = read_port(regno_read1); 
    assign read_data2 = read_port(regno_read2);

endmodule
