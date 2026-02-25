import os
import re
import argparse

# Define constants
REGISTERS = [
    "$zero", "$at", "$v0", "$a0", "$a1", "$a2", "$t0", "$t1",
    "$t2", "$s0", "$s1", "$s2", "$k0", "$sp", "$fp", "$ra"
]

# Define patterns
LABEL_REGEX = re.compile(r"^([A-Za-z][_A-Za-z0-9]*):")
NUMBER_REGEX = re.compile(r"-?(0?x)?([0-9A-Fa-f]+)")
PSEUDO_OP_REGEX = re.compile(rf"(({LABEL_REGEX.pattern})?\s*\.(fill|word)\s+({NUMBER_REGEX.pattern})\s*)")

# Define Args
VERBOSE = False
SAVE_INST = False

ASSEMBLY_FILE = ""
ISA_FILE = ""
INSTRUCTION_FILE = None # Filtered out comments, whitespace, & mis-formatting
OUT_TYPE = ""

# Define variables
symbol_table = {}

verbose = lambda s: print(s) if VERBOSE else None

# Utility functions
def remove_comment(line):
    return re.split(r"(;|!|//|#)", line)[0].strip()

def hex_to_bin(hex):
    s = ''
    for c in hex:
        i = int(c, 16)
        s += f"{i // 8}{i // 4 % 2}{i // 2 % 2}{i % 2}"
    return s


def print_inst(inst):
    if SAVE_INST:
        INSTRUCTION_FILE.write(inst)

def save_sym_table(output_file):
    length = 0
    for key in symbol_table:
        length = max(length, len(key))
    with open(f"{output_file}.sym", "w") as out:
        out.writelines([f"{key:<{length + 3}}: {hex(symbol_table[key])}\n" for key in symbol_table])

def parse_i20(target, line_number):
    try:
        offset = int(target, 0) if target.startswith(('0x', '-0x')) else int(target)
    except ValueError:
        if target not in symbol_table:
            offset = None
        else:
            offset = symbol_table.get(target) - (line_number + 1)
    if offset is None:
        return None
    return f"{offset & 0xFFFFF:05X}"

# Parse an ISA definition line
def parse_isa(line):
    regex, machine_code = map(str.strip, line.split(":"))
    match = re.match(r'^([a-z]+)\s*', regex)
    mnemonic = match.group(1) if match else None
    syntax = {
        "$X": r"(?P<X>\$[a-z]+[0-9]*)",
        "$Y": r"(?P<Y>\$[a-z]+[0-9]*)",
        "$Z": r"(?P<Z>\$[a-z]+[0-9]*)",
        "#I": rf"(?P<I>{NUMBER_REGEX.pattern})",
        "%O": rf"(?P<O>([_a-zA-Z][_a-zA-Z0-9]*|{NUMBER_REGEX.pattern}))",
        ",": r"\s*,\s*",
        " ": r"\s+",
    }
    for k, v in syntax.items():
        regex = regex.replace(k, v)
    return re.compile(rf"({LABEL_REGEX.pattern})?\s*{regex}", re.IGNORECASE), machine_code.replace(" ", ""), mnemonic

# Assemble a single instruction
def assemble(instruction, inst_number, line_number):
    mnemonic = re.split(r'\s+', instruction.split(":")[-1].strip())[0]
    pseudo = PSEUDO_OP_REGEX.match(instruction)
    if pseudo:
        print_inst(instruction.split(":")[-1].strip() + "\n")
        return pseudo.groups()[-1].rjust(8, '0')
    for regex, machine_code, isa_mnemonic in isa:
        if isa_mnemonic.lower() != mnemonic.lower():
            continue
        match = regex.fullmatch(instruction)
        if not match:
            break
        result = machine_code
        for placeholder in re.findall(r"[G-Z]", machine_code):
            target = match.group(placeholder)
            if placeholder in "IO":
                replacement = parse_i20(target, inst_number if placeholder == "O" else 0)
                if not replacement:
                    return f"line {line_number}: Undefined label `{target}`"
            elif placeholder in "XYZ":
                try:
                    index = REGISTERS.index(target)
                except ValueError:
                    return f"line {line_number}: Unknown register `{target}`"
                replacement = f"{index:X}"
            else:
                return f"line {line_number}: Undefined token `{placeholder}`"
            result = result.replace(placeholder, replacement)
        print_inst(instruction.split(":")[-1].strip() + "\n")
        return result.rjust(8, '0')
    return f"line {line_number}: `{instruction}` does not match any instruction from the {ISA_FILE}"

# Pass 1: Create the symbol table
def pass1(file_path):
    line_number = 0
    with open(f"{file_path}.s") as f:
        for line in f:
            clean_line = remove_comment(line)
            match = LABEL_REGEX.match(clean_line)
            if match:
                symbol_table[match.group(1)] = line_number
            if clean_line and not LABEL_REGEX.fullmatch(clean_line):
                line_number += 1
    return symbol_table

# Pass 2: Assemble the program
def pass2(file_name):
    results = []
    inst_num = 0
    line_num = 1
    hex_str = re.compile(r'[0-9a-fA-F]{8}')
    with open(f"{file_name}.s") as f:
        for line in f:
            instruction = remove_comment(line)
            if instruction and not LABEL_REGEX.fullmatch(instruction):
                results.append(assemble(instruction, inst_num, line_num))
                inst_num += 1
            line_num += 1
    errors = [r for r in results if not hex_str.match(r)]
    if errors:
        print(f"Assembler Error for {file_name}.s")
        for error in errors:
            print(f"\t{error}")
        return None
    with open(f"{file_name}.hex", "w") as out:
        out.writelines(f"{r}\n" for r in results if hex_str.match(r))
    with open(f"{file_name}.bin", "w") as out:
        out.writelines(f"{hex_to_bin(r)}\n" for r in results if hex_str.match(r))

# Load the ISA
def load_isa(path):
    with open(path) as f:
        return [parse_isa(line) for line in f if line.strip()]

if __name__ == "__main__":
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Assembles generic ISA-defined assembly code into hex or binary")
    parser.add_argument("asm_file", help="Path to the input assembly file (e.g., pow.s)", default="pow.s")
    parser.add_argument(
        "-i",
        "--isa",
        required=True,
        type=str,
        default="isa",
        help="define the ISA file to load",
    )
    parser.add_argument(
        "-s",
        "--save",
        required=False,
        type=str,
        help="define the instruction file to save to",
    )

    # Parse the command-line arguments
    args = parser.parse_args()
    ISA_FILE = args.isa
    file_name, extension = os.path.splitext(args.asm_file)
    if extension != '.s':
        raise ValueError('Input file must be assembly (*.s)')

    if args.save:
        if not args.save.endswith(".s"):
            print("Error: Save file must be a .s file.")
            exit()
        SAVE_INST = True
        INSTRUCTION_FILE = open(args.save, "w", encoding="UTF8")

    # Load the ISA
    isa = load_isa(ISA_FILE)

    # Perform both passes and save machine code to files (*.hex & *.bin)
    pass1(file_name)
    pass2(file_name)

    # Save the symbol table to a file (*.sym)
    save_sym_table(file_name)
