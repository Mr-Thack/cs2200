module test;
    logic clk;
    logic rst;

    // pipeline #( .MEM_SIZE(256) ) dut (
    pipeline dut (
        .clk(clk),
        .rst(rst)
    );

    // Clock oscillates every 5 time units, so clock cycle = 10 time units.
    always #5 clk = ~clk;

    initial begin
        // Record here
        $dumpfile("build/waves.vcd"); 
        $dumpvars(0, test);

        // Reset everything for 3 clock cycles
        clk = 1'b0;
        rst = 1'b1;
        #30;
        rst = 1'b0;
        // Run for 6500 clock cycles 
        #65000;

        $display("Finished Test");
        $finish;
    end
endmodule
