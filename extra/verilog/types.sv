package types;

    // 3 bit Operation Code
    typedef enum logic [2:0] {
        ALU_IGNORE,
        ALU_ADD,
        ALU_SUB,
        ALU_NAND,
        ALU_PASSA,
        ALU_PASSB,
        ALU_ADD1
    } alu_operation;

    typedef enum logic [1:0] {
        ALU_VAL1,
        ALU_VAL2,
        ALU_OFFSET,
        ALU_PC
    } alu_source;
    

    typedef enum logic [1:0] {
        MEM_IGNORE,
        MEM_READ,
        MEM_WRITE
    } mem_operation;

    typedef enum logic [2:0] {
        CMP_IGNORE,
        CMP_LT,
        CMP_EQ,
        CMP_GT
    } cmp_operation;

    typedef enum logic [2:0] {
        LOGIC_IGNORE,
        LOGIC_JMP_OFFSET,
        LOGIC_JMP_RES
    } logic_operation;


    typedef enum logic [3:0] {
        OP_ADD  = 4'b0000,
        OP_NAND = 4'b0001,
        OP_ADDI = 4'b0010,
        OP_LW   = 4'b0011,
        OP_SW   = 4'b0100,
        OP_BEQ  = 4'b0101,
        OP_JALR = 4'b0110,
        OP_HALT = 4'b0111,
        OP_BGT  = 4'b1000,
        OP_LEA  = 4'b1001
    } opcode_t;
    
    typedef struct packed {
        logic [15:0] unused;
        logic [3:0] rz;
    } immediate_value;

    typedef struct packed {
        opcode_t opcode;
        logic [3:0] rx;
        logic [3:0] ry;
        immediate_value imm;
    } instruction_data;

    typedef struct packed {
        logic [31:0] pc_plus_1;
        instruction_data instruction;
        logic predicted_taken;
        logic btb_hit; // This is just for profiling
        logic valid; // Also for profiling
    } fbuf_data;

    typedef struct packed {
        logic [31:0] pc_plus_1;
        logic [31:0] val1;
        logic [31:0] val2;
        logic [31:0] offset;
        logic [3:0] dr;
        logic [3:0] sr1;
        logic [3:0] sr2;
        alu_source src1;
        alu_source src2;
        alu_operation aluop;
        cmp_operation cmpop;
        logic_operation logop;
        mem_operation memop;
        logic predicted_taken;
        logic btb_hit; // Just for profiling
        logic valid; // Also for profiling
    } dbuf_data;


    // For the Memory Stage,
    // I actually found it more logical
    // to add a mux onto the data line instead of the address line
    // Both would work, and I don't think there's a major improvement either way
    typedef struct packed {
        logic [31:0] address;
        logic [31:0] data;
        logic [3:0] dr;
        mem_operation memop; 
        logic valid;
    } ebuf_data;

    typedef struct packed {
        logic [31:0] data;
        logic [3:0] dr;
        logic valid;
    } mbuf_data;
    
    typedef struct packed {
        logic [31:0] target;
        logic take;
        logic valid;
    } btb_read_data;

    typedef struct packed {
        logic [31:0] pc;
        logic [31:0] target; 
        logic taken;
        logic write;
    } btb_write_data;

endpackage
