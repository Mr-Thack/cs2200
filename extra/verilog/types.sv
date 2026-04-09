package types;

    typedef logic [31:0] word;

    // 3 bit Operation Code
    typedef enum logic [2:0] {
        ALU_ADD,
        ALU_SUB,
        ALU_NAND,
        ALU_ADD1,
        ALU_PASSA,
        ALU_PASSB,
        ALU_IGNORE
    } alu_operation;



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
        OP_LEA  = 4'b1001,
        OP_MIN  = 4'b1010,
        OP_MAX  = 4'b1011
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
        word pc_plus_1;
        instruction_data instruction;
    } fbuf_data;

    typedef struct packed {
        word pc_plus_1;
        opcode_t opcode;
        word val1;
        word val2;
        word offset;
        logic [3:0] dr;
        logic [3:0] sr1;
        logic [3:0] sr2;
    } dbuf_data;


    // For the Memory Stage,
    // I actually found it more logical
    // to add a mux onto the data line instead of the address line
    // Both would work, and I don't think there's a major improvement either way
    typedef struct packed {
        opcode_t opcode;
        word address;
        word data;
        logic [3:0] dr;
    } ebuf_data;

    typedef struct packed {
        word data;
        logic [3:0] dr;
    } mbuf_data;

endpackage
