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

        fork
            begin
                wait(dut.halt_flag == 1'b1);
                #10; // Wait 1 cycle to ensure everything is latched
                $display("     Cycles: %0d", dut.out_stat_cycles);
                $display("  Instructions: %0d", dut.stat_logical_inst_retired);

                // Calculate and print CPI
                $display("     CPI: %0.5f", real'(dut.out_stat_cycles) / real'(dut.stat_logical_inst_retired));
            end
            begin
                // Run for 6000 clock cycles 
                #60000;
                $display("FAILED TO HALT");
            end
        join_any

        $finish;
    end
endmodule
