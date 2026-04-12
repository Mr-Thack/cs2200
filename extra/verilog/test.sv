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

        // By default, the registers are not dumped on a wire
        // And the testing software only dumps the outputs of wires onto the
        // waves file, I guess because we could have like infinite registers,
        // which would overload our stuff.
        // So... we have to manually dump the things we want
        for (int i = 0; i < 16; i++) begin
            $dumpvars(0, dut.registers.registers[i]);
        end

        // Reset everything for 3 clock cycles
        clk = 1'b0;
        rst = 1'b1;
        #30;
        rst = 1'b0;
        // Run for 1500 clock cycles 
        #15000;

        $display("Finished Test");
        $finish;
    end
endmodule
