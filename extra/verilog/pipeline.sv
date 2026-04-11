module pipeline (
    input logic clk,
    input logic rst,

    output logic [31:0] debug_pc,
    output logic halt_flag,
    output logic [31:0] out_stat_cycles
);

// Everything is defined left to right

// ************ //
// GLOBAL LOGIC //
// ************ //

logic [31:0] PC;

// Stop forever for halting
logic halt_now;
// Stop for a load-use hazard
logic stall_now;
logic sig_halt;

logic branch_true;
logic [31:0] branch_target_line;

logic [3:0] write_reg_dest;
logic [31:0] write_reg_data;


fbuf_data fbuf_in, fbuf_out;
dbuf_data dbuf_in, dbuf_out;
ebuf_data ebuf_in, ebuf_out;
mbuf_data mbuf_in, mbuf_out;

always_ff @(posedge clk) begin
    if (rst) begin
        halt_now <= 1'b0;
    end else if (sig_halt) begin
        // As soon as we get HALT in the decode stage,
        // latch onto the STALL forever and forever.
        halt_now <= 1'b1;
    end

    if (rst) begin
        PC <= 32'd0;
    end else if (!halt_now && !stall_now) begin
        // We ONLY want to change PC if we're not Stalled
        PC <= branch_true? branch_target_line : (PC + 1);
    end
end

// ********** //
// PERF STATS //
// ********** //
logic [31:0] stat_cycles;
logic [31:0] stat_stalls;
logic [31:0] stat_flushes;
logic [31:0] stat_branches_seen;
logic [31:0] stat_branches_correct;
logic [31:0] stat_branches_incorrect;

always_ff @(posedge clk) begin
    if (rst) begin
        stat_cycles <= '0;
        stat_stalls <= '0;
        stat_flushes <= '0;
        stat_branches_seen <= '0;
        stat_branches_correct <= '0;
        stat_branches_incorrect <= '0;
    end else begin
        if (!halt_now) stat_cycles <= stat_cycles + 1;

        if (stall_now) stat_stalls <= stat_stalls + 1;

        // If branch_true, then our policy of predicting not taken was wrong
        if (branch_true) stat_flushes <= stat_flushes + 1;

        if (dbuf_out.logop == LOGIC_JMP_OFFSET) begin
            stat_branches_seen <= stat_branches_seen + 1;
            // If not branch_true, then we were correct in prredicting not taken
            if (!branch_true) stat_branches_correct <= stat_branches_correct + 1;

            stat_branches_incorrect <= stat_branches_seen - stat_branches_correct;
        end
    end
end

// These are here to force Yosys to compile this module
assign debug_pc = PC;
assign halt_flag = halt_now;
assign out_stat_cycles = stat_cycles;

// ********************* //
// INLINED MEMORY ARRAYS //
// ********************* //

localparam MEM_SIZE = 65536;

(* nomem2reg *) logic [31:0] IMEM [MEM_SIZE];
(* nomem2reg *) logic [31:0] DMEM [MEM_SIZE];

// Load from Init ROM
initial begin
    $readmemh("../pow.hex", IMEM);
    $readmemh("../pow.hex", DMEM);
end

// *********** //
// FETCH STAGE //
// *********** //

// This wire is the output from imem
logic [31:0] instruction_read_line;


assign instruction_read_line = IMEM[PC[15:0]];

always_comb begin
    fbuf_in.pc_plus_1 = PC + 1;
    fbuf_in.instruction = instruction_read_line;
end

always_ff @(posedge clk) begin
    // If Stalled,
    // then we can't forward our newly fetched instruction to the Decode Stage
    if (!halt_now && !stall_now) begin
        fbuf_out <= (rst || branch_true) ? '0 : fbuf_in;
    end
end


// ************ //
// DECODE STAGE //
// ************ //

logic [31:0] dout1, dout2;

decode dec(
    .fbuf(fbuf_out),
    .dbuf(dbuf_in),
    .*
);

// Physically instantiate and read/write registers
dprf registers(
    .clk(clk),
    .rst(rst),
    .we('1),
    .regno_read1(dbuf_in.sr1),
    .regno_read2(dbuf_in.sr2),
    .regno_write(write_reg_dest),
    .write_data(write_reg_data),
    .read_data1(dout1),
    .read_data2(dout2)
);


assign stall_now = (dbuf_out.dr != 4'd0) && (dbuf_out.memop == MEM_READ)
                    && ((dbuf_out.dr == dbuf_in.sr1) || (dbuf_out.dr == dbuf_in.sr2));


always_ff @(posedge clk) begin
    // Need to check halt_now and dbuf_out.opcode because
    // halt_now is only latched on the clock cycle, so it wouldn't propogate
    // fast enough to prevent the decode stage from forwarding this
    dbuf_out <= (rst || halt_now || stall_now || sig_halt) ? '0 : dbuf_in;
end

// ************* //
// EXECUTE STAGE //
// ************* //


// We need to calculate the forwarded values
// And we might overwrite the alu_val's
// But then use the forwarded values later / elsewhere (like in SW)
// So, we need to keep these separate.
logic [31:0] fwd_val1;
logic [31:0] fwd_val2;

always_comb begin
    fwd_val1 = dbuf_out.val1;
    fwd_val2 = dbuf_out.val2;

    // So... we need to do Data Forwarding
    // But ummm.... as of the time I'm writing, I'm too tired to modularize
    // So, remember to copy and paste and edit properly!!!

    // Also, the diagram put this before the DBUF,
    // but we're doing this afterwards and overwriting the data from dbuf
    // because the data is latched at the end of the cycle,
    // so we would want to wait until after the EX and MEM stages are done,
    // so that they can latch their data into the buffer and then we forward.
    // Oh wait, I could have also checked mbuf_in and ebuf_in instead...
    // Then I could've done what the diagram did and forward at the end of the
    // decode stage before the execute stage.
    // Oh well! This works and I don't care anymore!

    // 1. Check Results of Memory Stage First (older data, so lower priority)
    if ((mbuf_out.dr != 4'd0) && (mbuf_out.dr == dbuf_out.sr1)) begin
        fwd_val1 = mbuf_out.data;
    end
    if ((mbuf_out.dr != 4'd0) && (mbuf_out.dr == dbuf_out.sr2)) begin
        fwd_val2 = mbuf_out.data;
    end

    // 2. Check Results of Execute Stage Second (newer data, so higher priority)
    // Overwrites any forwarding from the memory stage
    if ((ebuf_out.dr != 4'd0) && (ebuf_out.dr == dbuf_out.sr1)) begin
        fwd_val1 = ebuf_out.data;
    end
    if ((ebuf_out.dr != 4'd0) && (ebuf_out.dr == dbuf_out.sr2)) begin
        fwd_val2 = ebuf_out.data;
    end
end

execute exec(
    .dbuf(dbuf_out),
    .ebuf(ebuf_in),
    .*
);

always_ff @(posedge clk) begin
    ebuf_out <= rst ? '0 : ebuf_in;
end

// ********* //
// MEM STAGE //
// ********* //

logic [15:0] dmem_addr_line;
logic [31:0] dmem_data_line;

assign dmem_addr_line = ebuf_out.address[15:0];
assign dmem_data_line = DMEM[dmem_addr_line];


always_ff @(posedge clk) begin
    if (ebuf_out.memop == MEM_WRITE) begin
        DMEM[dmem_addr_line] <= ebuf_out.data;
    end
end

always_comb begin
    mbuf_in.dr = ebuf_out.dr;
    mbuf_in.data = (ebuf_out.memop == MEM_READ) ? dmem_data_line : ebuf_out.data;
end

always_ff @(posedge clk) begin
    mbuf_out <= rst ? '0 : mbuf_in;
end

// **************** //
// WRITE BACK STAGE //
// **************** //

always_comb begin
   write_reg_dest = mbuf_out.dr;
   write_reg_data = mbuf_out.data;
end

endmodule
