import argparse
import csv
import os.path
import re
from abc import ABC, abstractmethod
from typing import Final, Union

# Python 2: remap input to raw_input and range to xrange
try:
    input = raw_input
    range = xrange
except NameError:
    pass


class Device(ABC):
    @abstractmethod
    def __init__(self):
        """
        Initializer function. Should override and set the self.device_id and self.int variables.
        """
        pass

    @abstractmethod
    def sim_cycles(self, cycles: int) -> None:
        """
        Simulate multiple cycles. Should override and update the self.int variable to True if interrupting.
        """
        pass

    def on_ack(self) -> None:
        """
        Simulate acknowledge. Override if function needed. Does not need to reset self.int
        """
        pass

    def on_in(self) -> Union[int, None]:
        """
        Simulate IN instruction with this devices' device_id. Override if need functionality.
        """
        pass


class Timer(Device):
    def __init__(self):
        self.device_id: Final[int] = 0
        self.int: bool = False
        self.ctr: int = 0

    def sim_cycles(self, cycles: int):
        self.ctr += cycles
        if self.ctr >= 0x7D0:
            self.ctr = 0x7D0
            self.int = True

    def on_ack(self):
        self.ctr = 0


class DistanceTracker(Device):
    def __init__(self):
        self.device_id: Final[int] = 1
        self.int: bool = False
        self.ctr: int = 0
        self.idx: int = -1
        self.outputs: list[int] = [
            0x009CE117,
            0x0082B93F,
            0x00FF9FCE,
            0x0073BD2B,
            0x00377B65,
            0x0058B86E,
            0x0000D114,
            0x00BB525B,
            0x00C9E7B9,
            0x00E4ED1C,
            0x00E3EBA7,
            0x0004C2C6,
            0x0093FAA4,
            0x00D14DD6,
            0x00AE6D38,
            0x0068476C,
        ]

    def sim_cycles(self, cycles: int):
        self.ctr += cycles
        if self.ctr >= 0x5DC:
            self.ctr = 0x5DC
            if not self.int:
                self.idx += 1
            self.int = True

    def on_ack(self):
        self.ctr = 0

    def on_in(self):
        return self.outputs[self.idx % len(self.outputs)]


MIN_PC = 8
PC = MIN_PC
MEM = {}
REGS = {
    0: 0,
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
    6: 0,
    7: 0,
    8: 0,
    9: 0,
    10: 0,
    11: 0,
    12: 0,
    13: 0,
    14: 0,
    15: 0,
}
DEVICES = [Timer(), DistanceTracker()]
IE = False  # Interrupts enabled register

OP_NAME = {
    "0000": "ADD",
    "0001": "NAND",
    "0010": "ADDI",
    "0011": "LW",
    "0100": "SW",
    "0101": "BEQ",
    "0110": "JALR",
    "0111": "HALT",
    "1000": "BGT",
    "1001": "LEA",
    "1010": "MIN",
    "1011": "MAX",
    "1101": "EI/DI",
    "1110": "IN",
    "1111": "RETI",
}
REG_NAME = {
    "0000": "$zero",
    "0001": "$at",
    "0010": "$v0",
    "0011": "$a0",
    "0100": "$a1",
    "0101": "$a2",
    "0110": "$t0",
    "0111": "$t1",
    "1000": "$t2",
    "1001": "$s0",
    "1010": "$s1",
    "1011": "$s2",
    "1100": "$k0",
    "1101": "$sp",
    "1110": "$fp",
    "1111": "$ra",
}
BREAKPOINTS = []
LABELS = {}

HALTED = False
QUIT = False

SAVE_REG = False
csv_writer = None
instr_file = None

LAST_CMD = "help"


def uint(binary):
    return int(binary, 2)


def int2c(binary):
    return force_signed(uint(binary), len(binary))


def truncate_int(num, bits):
    return num % (2**bits)


def force_signed(num, bits):
    num = truncate_int(num, bits)
    if (1 << bits - 1) & num:
        return num - (1 << bits)
    else:
        return num


def force_unsigned(num, bits):
    return ((1 << bits) - 1) & num


def load_program(runfile):
    addr = 0
    with open(runfile, "r") as f:
        for line in f:
            # parse binary string into integer and strip newline
            MEM[addr] = int(line[:-1], 2)
            addr += 1

    last_period_index = runfile.rfind(".")
    symfile = runfile[:last_period_index] + ".sym"
    if os.path.isfile(symfile):
        with open(symfile, "r") as f:
            for line in f:
                symbol_regex = r"(\w+)\s*: 0[xX]([0-9a-fA-F]+)"
                symbol_m = re.match(symbol_regex, line)
                label = symbol_m.group(1)
                addr = int(symbol_m.group(2), 16)
                LABELS[addr] = label
    else:
        print(
            "WARNING: No symbol file available at {}, continuing without symbolic debugging".format(
                symfile
            )
        )


def access_mem(addr):
    max_addr = 2**24
    if addr > max_addr - 1:
        addr = addr % max_addr
    try:
        return MEM[addr]
    except KeyError:
        return 0


def print_sim_state():
    global PC, IE
    print(
        " ze {:08X} {:<12} a1 {:08X} {:<12} t2 {:08X} {:<12} k0 {:08X} {:<12}".format(
            REGS[0],
            reg_contents(0),
            REGS[4],
            reg_contents(4),
            REGS[8],
            reg_contents(8),
            REGS[12],
            reg_contents(12),
        )
    )
    print(
        " at {:08X} {:<12} a2 {:08X} {:<12} s0 {:08X} {:<12} sp {:08X} {:<12}".format(
            REGS[1],
            reg_contents(1),
            REGS[5],
            reg_contents(5),
            REGS[9],
            reg_contents(9),
            REGS[13],
            reg_contents(13),
        )
    )
    print(
        " v0 {:08X} {:<12} t0 {:08X} {:<12} s1 {:08X} {:<12} fp {:08X} {:<12}".format(
            REGS[2],
            reg_contents(2),
            REGS[6],
            reg_contents(6),
            REGS[10],
            reg_contents(10),
            REGS[14],
            reg_contents(14),
        )
    )
    print(
        " a0 {:08X} {:<12} t1 {:08X} {:<12} s2 {:08X} {:<12} ra {:08X} {:<12}".format(
            REGS[3],
            reg_contents(3),
            REGS[7],
            reg_contents(7),
            REGS[11],
            reg_contents(11),
            REGS[15],
            reg_contents(15),
        )
    )
    print(
        " ie {:<21} timer_int {:<14} tracker_int {}".format(
            str(bool(IE)), str(bool(DEVICES[0].int)), str(bool(DEVICES[1].int))
        )
    )
    print(" - Now at x{:08X}: {}".format(PC, print_instruction()))


def save_reg_states():
    global PC
    csv_writer.writerow(
        ["{:X}".format(PC)] + ["{:X}".format(REGS[i]) for i in range(1, 16)]
    )


def reg_contents(i):
    try:
        return "{:.11}".format(LABELS[REGS[i]])
    except:
        return "{}".format(force_signed(REGS[i], 32))


def bit(instr, bit):
    return instr[31 - bit]


def bit_range(instr, high, low):
    # b/c we're using strings, math is reversed order
    return instr[31 - high : 31 - low + 1]


def print_instruction():
    global PC
    instruction = access_mem(PC)
    IREG = format(instruction, "032b")
    op = bit_range(IREG, 31, 28)

    if IREG == "00000000000000000000000000000000":
        return "noop"

    if (
        op == "0000" or op == "0001" or op == "1010" or op == "1011"
    ):  # ADD, NAND, MIN, MAX
        dr = bit_range(IREG, 27, 24)
        sr1 = bit_range(IREG, 23, 20)
        sr2 = bit_range(IREG, 3, 0)
        return "{} {}, {}, {}".format(
            OP_NAME[op], REG_NAME[dr], REG_NAME[sr1], REG_NAME[sr2]
        )
    elif op == "0010":  # ADDI
        dr = bit_range(IREG, 27, 24)
        sr1 = bit_range(IREG, 23, 20)
        immval = bit_range(IREG, 19, 0)
        return "{} {}, {}, #{}".format(
            OP_NAME[op], REG_NAME[dr], REG_NAME[sr1], int2c(immval)
        )
    elif op == "0011" or op == "0100":  # LW, SW
        dr = bit_range(IREG, 27, 24)
        base_r = bit_range(IREG, 23, 20)
        offset = bit_range(IREG, 19, 0)
        return "{0} {1}, #{3}({2})".format(
            OP_NAME[op], REG_NAME[dr], REG_NAME[base_r], int2c(offset)
        )
    elif op == "0101" or op == "1000":  # BEQ, BGT
        sr1 = bit_range(IREG, 27, 24)
        sr2 = bit_range(IREG, 23, 20)
        addr = bit_range(IREG, 19, 0)
        return "{} {}, {}, 0x{:06X}".format(
            OP_NAME[op], REG_NAME[sr1], REG_NAME[sr2], uint(addr)
        )
    elif op == "0110":  # JALR
        at = bit_range(IREG, 27, 24)
        ra = bit_range(IREG, 23, 20)
        return "{} {}, {}".format(OP_NAME[op], REG_NAME[at], REG_NAME[ra])
    elif op == "0111" or op == "1111":  # HALT, RETI
        return OP_NAME[op]
    elif op == "1001" or op == "1110":  # LEA, IN
        dr = bit_range(IREG, 27, 24)
        offset = bit_range(IREG, 19, 0)
        return "{} {}, 0x{:05X}".format(OP_NAME[op], REG_NAME[dr], int2c(offset))
    elif op == "1101":  # EI/DI
        bit20 = bit_range(IREG, 20, 20)
        return "EI" if bit20 == "0" else "DI"
    else:
        return "Unrecognized instruction"


def print_help():
    print(
        """ Welcome to the simulator text interface. The available commands are:

    r[un] or c[ontinue]             resume execution until next breakpoint
    s[tep]                          execute one instruction
    b[reak] <addr or label>         view and set breakpoints
                                    ex) 'break'
                                    ex) 'break 0x3'
                                    ex) 'break main'
    print <lowaddr>-<highaddr>      print the values in memory between <lowaddr> and <highaddr>
                                    ex) 'print 0x20-0x30'
    q[uit]                          exit the simulator
    """
    )


def run():
    global HALTED
    while HALTED == False:
        try:
            step_instruction()
        except RuntimeError as err:
            print(f"Panic: {err}")
            break

        if PC in BREAKPOINTS:
            break


def step_instruction():
    global PC, IE
    PC = max(PC, MIN_PC)  # Ensure PC is always at least MIN_PC

    # Check if interrupt
    if IE == True:
        for device in DEVICES:
            if device.int:  # Interrupt macrostate
                device.on_ack()
                REGS[12] = PC
                IE = False
                device.int = False
                PC = access_mem(device.device_id)
                return

    instruction = access_mem(PC)
    PC += 1
    # decode instruction
    IREG = format(instruction, "032b")

    op = bit_range(IREG, 31, 28)

    if OP_NAME[op] == "ADD":
        dr_regno = uint(bit_range(IREG, 27, 24))
        sr1_regno = uint(bit_range(IREG, 23, 20))
        sr2_regno = uint(bit_range(IREG, 3, 0))
        num = force_signed(REGS[sr1_regno], 32) + force_signed(REGS[sr2_regno], 32)
        res = force_unsigned(num, 32)
        REGS[dr_regno] = res

    elif OP_NAME[op] == "NAND":
        dr_regno = uint(bit_range(IREG, 27, 24))
        sr1_regno = uint(bit_range(IREG, 23, 20))
        sr2_regno = uint(bit_range(IREG, 3, 0))
        num = ~(REGS[sr1_regno] & REGS[sr2_regno])
        res = force_unsigned(num, 32)
        REGS[dr_regno] = res

    elif OP_NAME[op] == "ADDI":
        dr_regno = uint(bit_range(IREG, 27, 24))
        sr1_regno = uint(bit_range(IREG, 23, 20))
        immval_int = int2c(bit_range(IREG, 19, 0))
        num = force_signed(REGS[sr1_regno], 32) + immval_int
        res = force_unsigned(num, 32)
        REGS[dr_regno] = res

    elif OP_NAME[op] == "LW":
        dr_regno = uint(bit_range(IREG, 27, 24))
        base_regno = uint(bit_range(IREG, 23, 20))
        offset_int = int2c(bit_range(IREG, 19, 0))
        res = access_mem(force_unsigned(REGS[base_regno] + offset_int, 32))
        REGS[dr_regno] = res

    elif OP_NAME[op] == "SW":
        sr_regno = uint(bit_range(IREG, 27, 24))
        base_regno = uint(bit_range(IREG, 23, 20))
        offset_int = int2c(bit_range(IREG, 19, 0))
        MEM[force_unsigned(REGS[base_regno] + offset_int, 32)] = REGS[sr_regno]

    elif OP_NAME[op] == "LEA":
        dr_regno = uint(bit_range(IREG, 27, 24))
        offset_int = int2c(bit_range(IREG, 19, 0))
        REGS[dr_regno] = force_unsigned(PC + offset_int, 32)

    elif OP_NAME[op] == "JALR":
        at_regno = uint(bit_range(IREG, 27, 24))
        ra_regno = uint(bit_range(IREG, 23, 20))
        REGS[ra_regno] = PC
        PC = REGS[at_regno]

    elif OP_NAME[op] == "HALT":
        # undo last pcinc
        PC -= 1
        global HALTED
        HALTED = True

    elif OP_NAME[op] == "BEQ":
        sr1_regno = uint(bit_range(IREG, 27, 24))
        sr2_regno = uint(bit_range(IREG, 23, 20))
        offset_int = int2c(bit_range(IREG, 19, 0))
        if REGS[sr1_regno] == REGS[sr2_regno]:
            PC = force_unsigned(PC + offset_int, 32)

    elif OP_NAME[op] == "BGT":
        sr1_regno = uint(bit_range(IREG, 27, 24))
        sr2_regno = uint(bit_range(IREG, 23, 20))
        offset_int = int2c(bit_range(IREG, 19, 0))
        if force_signed(REGS[sr1_regno], 32) > force_signed(REGS[sr2_regno], 32):
            PC = force_unsigned(PC + offset_int, 32)

    elif OP_NAME[op] == "MIN":
        dr_regno = uint(bit_range(IREG, 27, 24))
        sr1_regno = uint(bit_range(IREG, 23, 20))
        sr2_regno = uint(bit_range(IREG, 3, 0))
        res = min(force_signed(REGS[sr1_regno], 32), force_signed(REGS[sr2_regno], 32))
        REGS[dr_regno] = force_unsigned(res, 32)

    elif OP_NAME[op] == "MAX":
        dr_regno = uint(bit_range(IREG, 27, 24))
        sr1_regno = uint(bit_range(IREG, 23, 20))
        sr2_regno = uint(bit_range(IREG, 3, 0))
        res = max(force_signed(REGS[sr1_regno], 32), force_signed(REGS[sr2_regno], 32))
        REGS[dr_regno] = force_unsigned(res, 32)

    elif OP_NAME[op] == "EI/DI":
        bit20 = bit_range(IREG, 20, 20)
        IE = bit20 == "0"

    elif OP_NAME[op] == "IN":
        dr_regno = uint(bit_range(IREG, 27, 24))
        device_id = int2c(bit_range(IREG, 19, 0))
        read = False
        for device in DEVICES:
            if device.device_id == device_id:
                REGS[dr_regno] = device.on_in()
                read = True
                break
        if not read:
            raise RuntimeError("Invalid device ID")

    elif OP_NAME[op] == "RETI":
        PC = REGS[12]  # PC = $k0
        IE = True

    # make sure zero register remains 0
    REGS[0] = 0
    if SAVE_REG and OP_NAME[op] != "HALT":
        save_reg_states()

    # step all devices
    for device in DEVICES:
        device.sim_cycles(10)  # Assuming all instructions take 10 cycles

    if PC in BREAKPOINTS:
        print("Breakpoint {} reached: PC = 0x{:X}".format(BREAKPOINTS.index(PC), PC))


def add_breakpoint(bp):
    try:
        bp = int(bp, 0)
    except ValueError:
        if bp in LABELS.values():
            # get PC val key by label value
            bp = list(LABELS.keys())[list(LABELS.values()).index(bp)]
    if bp not in BREAKPOINTS:
        BREAKPOINTS.append(bp)
    print("[sim] Added breakpoint: PC = 0x{:X}".format(bp))


def print_breakpoints():
    if len(BREAKPOINTS) > 0:
        for i, bp in enumerate(BREAKPOINTS):
            print("[sim] Breakpoint {}: PC = 0x{:X}".format(i, bp))
    else:
        print("[sim] No breakpoints currently enabled")


def print_mem(lowaddr, highaddr):
    for i in range(lowaddr, highaddr + 1):
        print("[0x{:X}]: 0x{:08X}".format(i, access_mem(i)))
    print("")


def prompt_input():
    global LAST_CMD
    break_regex = r"(break|b)\s*(.+)?"
    mem_regex = r"print (\w+)-(\w+)"

    input_command = input("(sim) ")

    # allow repeating commands by pressing enter GDB-style
    if input_command == "":
        input_command = LAST_CMD
    else:
        LAST_CMD = input_command

    if input_command == "help":
        print_help()
    elif input_command in ["run", "r"]:
        run()
    elif input_command in ["step", "s"]:
        step_instruction()
    elif input_command in ["continue", "c"]:
        run()
    elif input_command in ["quit", "q"]:
        global QUIT
        QUIT = True
    elif re.match(break_regex, input_command):
        try:
            m = re.match(break_regex, input_command)
            if m.group(2):
                bp = m.group(2)
                add_breakpoint(bp)
            print_breakpoints()
        except:
            print("[sim] Error parsing requested breakpoint: {}".format(input_command))
    elif re.match(mem_regex, input_command):
        try:
            m = re.match(mem_regex, input_command)
            lowaddr = int(m.group(1), 0)
            highaddr = int(m.group(2), 0)
            print_mem(lowaddr, highaddr)
        except:
            print("[sim] Error parsing requested print: {}".format(input_command))
    else:
        print("[sim] Unknown command: {}".format(input_command))
        print("[sim] For help on commands and usage, use the 'help' command")


def run_auto(show_prints=True):
    run()
    if show_prints:
        print("PC: {:08X}".format(PC))
        for n in range(0, len(REGS)):
            print("{0}: {1:08X}".format(REG_NAME["{0:04b}".format(n)], REGS[n]))
        for k, v in LABELS.items():
            print("{0}: {1:08X}".format(v, k))


def run_sim():
    global QUIT
    while QUIT == False:
        try:
            print_sim_state()
            prompt_input()
        except KeyboardInterrupt:
            print("[sim] Simulation interrupted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--auto", action="store_true", help="Run the simulator in autograder mode"
    )
    parser.add_argument("runfile", help=".bin file to be run")
    parser.add_argument("--save")
    parser.add_argument(
        "--init", help="The csv file that contains the initial register values"
    )

    parser.add_argument(
        "--hide-prints",
        required=False,
        action="store_true",
        help="If set, then a bunch of print statements will be suppressed.",
    )

    args = parser.parse_args()
    load_program(args.runfile)

    if args.init:
        if not args.init.endswith(".csv"):
            print("Inti file must be a .csv file")
            exit()
        with open(args.init, mode="r") as file:
            line = file.readline().strip()
            values = line.split(",")

            if len(values) != len(REGS):
                raise ValueError(
                    "The number of initial register values must match the number of registers"
                )
            else:
                REGS = {i: int(values[i], 16) for i in range(len(values))}

    if args.save:
        SAVE_REG = True
        if not args.save.endswith(".csv"):
            print("Save file must be a .csv file")
            exit()
        f = open(args.save, "w", encoding="UTF8", newline="")
        csv_writer = csv.writer(f)
    if not args.auto:
        run_sim()
    else:
        run_auto(not args.hide_prints)
