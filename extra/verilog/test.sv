module test;
    logic clk;
    logic rst;

    pipeline dut (
        .clk(clk),
        .rst(rst)
    );

    // Clock oscillates every 5 time units, so clock cycle = 10 time units.
    always #5 clk = ~clk;

    initial begin
        // Record here
        $dumpfile("waves.vcd"); 
        $dumpvars(0, test);

        // By default, the registers are not dumped on a wire
        // And the testing software only dumps the outputs of wires onto the
        // waves file, I guess because we could have like infinite registers,
        // which would overload our stuff.
        // So... we have to manually dump the things we want
        for (int i = 0; i < 16; i++) begin
            $dumpvars(0, dut.registers.registers[i]);
        end

        
        // $dumpvars(0, dut.dbuf_out.pc_plus_1);
        // $dumpvars(0, dut.dbuf_out.opcode);
        // $dumpvars(0, dut.dbuf_out.dr);
        // $dumpvars(0, dut.dbuf_out.val1);
        // $dumpvars(0, dut.dbuf_out.val2);
        // $dumpvars(0, dut.dbuf_out.offset);

        // Reset everything for 3 clock cycles
        clk = 1'b0;
        rst = 1'b1;
        #30;
        rst = 1'b0;
        // Run for 2000 clock cycles 
        #20000;

        $display("Finished Test");
        $finish;
    end
endmodule
