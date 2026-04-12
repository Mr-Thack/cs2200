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

logic branch_taken;
logic [31:0] branch_target;

logic predict_taken;
logic [31:0] predict_target;

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
        // Going by priority:
        
        // 1. If we need to flush (because branch mispredict)
        if (branch_taken) begin
            PC <= branch_target;

        // 2. Branch Prediction
        end else if (predict_taken) begin
            PC <= predict_target;

        // 3. Step Forward Normally
        end else begin
            PC <= PC + 1;
        end

    end
end

// ********** //
// PERF STATS //
// ********** //

// 1. Core Pipeline Metrics
logic [31:0] stat_cycles;
logic [31:0] stat_stalls;
logic [31:0] stat_flushes;
logic [31:0] stat_inst_retired;

// 2. BTB Cache Performance
logic [31:0] stat_btb_hits;
logic [31:0] stat_btb_misses;

// 3. Offset Branch Predictor Accuracy (BEQ / BGT)
logic [31:0] stat_branches_seen;
logic [31:0] stat_branches_correct;
logic [31:0] stat_branches_incorrect;

// 4. Indirect Jump Accuracy (JALR)
logic [31:0] stat_jalr_seen;
logic [31:0] stat_jalr_correct;
logic [31:0] stat_jalr_incorrect;


always_ff @(posedge clk) begin
    if (rst) begin
        stat_cycles <= '0;
        stat_stalls <= '0;
        stat_flushes <= '0;
        stat_inst_retired <= '0;

        stat_btb_hits <= '0;
        stat_btb_misses <= '0;

        stat_branches_seen <= '0;
        stat_branches_correct <= '0;
        stat_branches_incorrect <= '0;

        stat_jalr_seen <= '0;
        stat_jalr_correct <= '0;
        stat_jalr_incorrect <= '0;
    end else begin

        // -----------------------------------------
        // GLOBAL PIPELINE HEALTH
        // -----------------------------------------
        if (!halt_now) stat_cycles <= stat_cycles + 1;
        if (stall_now) stat_stalls <= stat_stalls + 1;
        if (branch_taken) stat_flushes <= stat_flushes + 1;
        if (mbuf_out.valid) begin
            // Count instructions that successfully make it out of the pipeline
            stat_inst_retired <= stat_inst_retired + 1;
        end

        // -----------------------------------------
        // CONDITIONAL BRANCHES (BEQ, BGT)
        // -----------------------------------------
        if (dbuf_out.logop == LOGIC_JMP_OFFSET) begin
            stat_branches_seen <= stat_branches_seen + 1;

            // Track BTB hit rate
            if (dbuf_out.btb_hit) begin
                stat_btb_hits <= stat_btb_hits + 1;
            end else begin
                stat_btb_misses <= stat_btb_misses + 1;
            end

            // Track Prediction Accuracy
            if (branch_taken) begin
                stat_branches_incorrect <= stat_branches_incorrect + 1;
            end else begin
                stat_branches_correct <= stat_branches_correct + 1;
            end
        end

        // -----------------------------------------
        // INDIRECT JUMPS (JALR)
        // -----------------------------------------
        if (dbuf_out.logop == LOGIC_JMP_RES) begin
            stat_jalr_seen <= stat_jalr_seen + 1;

            // Once RAS is implemented, this will track how well it works
            if (branch_taken) begin
                stat_jalr_incorrect <= stat_jalr_incorrect + 1;
            end else begin
                stat_jalr_correct <= stat_jalr_correct + 1;
            end
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

btb_read_data btb_rdata;
btb_write_data btb_wdata;

// BTB Indexing on PC, NOT ON PC + 1
btb btb0 (
    .clk(clk),
    .rst(rst),
    
    .read_pc(PC),
    .rdata(btb_rdata),

    .wdata(btb_wdata)
);

// *********** //
// FETCH STAGE //
// *********** //

// This wire is the output from imem
instruction_data IR;

assign IR = IMEM[PC[15:0]];

fetch ftch(
    .clk(clk),
    .rst(rst),
    .PC(PC),
    .IR(IR),
    .predict_taken(predict_taken),
    .predict_target(predict_target),
    .rdata(btb_rdata),
    .fbuf(fbuf_in)
);

always_ff @(posedge clk) begin
    // If Stalled,
    // then we can't forward our newly fetched instruction to the Decode Stage
    if (!halt_now && !stall_now) begin
        fbuf_out <= (rst || branch_taken) ? '0 : fbuf_in;
    end
end


// ************ //
// DECODE STAGE //
// ************ //

logic [31:0] dout1, dout2;

decode dec(
    .clk(clk),
    .rst(rst),
    .branch_taken(branch_taken),
    .halt_now(halt_now),
    .fbuf(fbuf_out),
    .dout1(dout1),
    .dout2(dout2),
    .sig_halt(sig_halt),
    .dbuf(dbuf_in)
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
    dbuf_out <= (rst || halt_now || stall_now || sig_halt || branch_taken) ? '0 : dbuf_in;
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
    .fwd_val1(fwd_val1),
    .fwd_val2(fwd_val2),
    .branch_taken(branch_taken),
    .branch_target(branch_target),
    .wdata(btb_wdata),
    .ebuf(ebuf_in)
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
    mbuf_in.valid = ebuf_out.valid;
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
