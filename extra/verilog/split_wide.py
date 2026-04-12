#!/usr/bin/env python3
"""
split_wide.py

Splits wide pipeline buffer signals in sv2v-generated Verilog by reading
struct definitions directly from a SystemVerilog types file.

Splits on FIELD BOUNDARIES, giving you named signals like:
    dbuf_out_pc_plus_1, dbuf_out_opcode, dbuf_out_val1, ...

Handles:
  - Internal reg/wire declarations
  - Port declarations (input/output wire/reg) in module bodies
  - Module port lists  (the `module foo(a, b, c);` header line)
  - Module instantiations:
        .fbuf(fbuf_out)  ->  .fbuf_pc_plus_1(fbuf_out_pc_plus_1),
                             .fbuf_instruction(fbuf_out_instruction), ...
  - Wide latch assignments using replication constants {N{...}}
  - Multi-module designs (each module handled independently)

Usage:
    python split_wide.py build/design.v --types types.sv [--dry-run]
"""

import re
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Parse types.sv
# ---------------------------------------------------------------------------

def parse_enum_widths(sv_text: str) -> dict:
    widths = {}
    for m in re.finditer(
        r'typedef\s+enum\s+logic\s+\[(\d+):(\d+)\]\s*\{[^}]*\}\s*(\w+)\s*;',
        sv_text
    ):
        hi, lo, name = int(m.group(1)), int(m.group(2)), m.group(3)
        widths[name] = hi - lo + 1
    return widths


def parse_structs(sv_text: str, enum_widths: dict) -> dict:
    """
    Returns {struct_type_name: [(field_name, bit_width), ...]}
    Fields in MSB-first order, matching sv2v packing.
    """
    structs = {}
    for sm in re.finditer(
        r'typedef\s+struct\s+packed\s*\{([^}]*)\}\s*(\w+)\s*;',
        sv_text, re.DOTALL
    ):
        body        = sm.group(1)
        struct_name = sm.group(2)
        fields      = []

        for line in body.strip().splitlines():
            line = line.split('//')[0]
            line = line.strip().rstrip(';').strip()

            if not line: 
                continue

            m = re.match(r'logic\s+\[(\d+):(\d+)\]\s+(\w+)', line)
            if m:
                fields.append((m.group(3), int(m.group(1)) - int(m.group(2)) + 1))
                continue

            m = re.match(r'logic\s+(\w+)$', line)
            if m:
                fields.append((m.group(1), 1))
                continue

            m = re.match(r'(\w+)\s+(\w+)$', line)
            if m:
                type_name, fname = m.group(1), m.group(2)
                if type_name in enum_widths:
                    fields.append((fname, enum_widths[type_name]))
                elif type_name in structs:
                    fields.append((fname, sum(w for _, w in structs[type_name])))
                else:
                    print(f"  WARNING: unknown type '{type_name}' for field "
                          f"'{fname}' in {struct_name}")
                continue
        structs[struct_name] = fields
    return structs


# ---------------------------------------------------------------------------
# Signal layout
# ---------------------------------------------------------------------------

class SignalLayout:
    """
    Maps a wide signal to its named field chunks.

    e.g. dbuf_out with dbuf_data fields becomes:
        dbuf_out_pc_plus_1 [31:0]
        dbuf_out_opcode    [3:0]
        dbuf_out_val1      [31:0]
        ...
    """
    def __init__(self, signal_name: str, fields: list):
        self.name        = signal_name
        self.fields      = fields           # [(field_name, width), ...]
        self.total_bits  = sum(w for _, w in fields)
        self.chunks      = [(f"{signal_name}_{fname}", w) for fname, w in fields]

        # Absolute bit ranges, MSB-first
        self.chunk_ranges = []
        cursor = self.total_bits - 1
        for (cname, w) in self.chunks:
            self.chunk_ranges.append((cname, cursor, cursor - w + 1, w))
            cursor -= w

    def resolve_slice(self, hi: int, lo: int) -> str:
        parts = []
        for (cname, chi, clo, cw) in self.chunk_ranges:
            overlap_hi = min(hi, chi)
            overlap_lo = max(lo, clo)
            if overlap_hi < overlap_lo:
                continue
            local_hi = overlap_hi - clo
            local_lo = overlap_lo - clo

            if local_hi == cw - 1 and local_lo == 0:
                parts.append(cname)
            elif local_hi == local_lo:
                parts.append(f"{cname}[{local_hi}]")
            else:
                parts.append(f"{cname}[{local_hi}:{local_lo}]")
        if not parts:
            raise ValueError(f"Empty slice [{hi}:{lo}] on {self.name}")
        return parts[0] if len(parts) == 1 else '{' + ', '.join(parts) + '}'


# ---------------------------------------------------------------------------
# Find wide signals in a module
# ---------------------------------------------------------------------------

def find_wide_signals(text: str, width_to_struct: dict, structs: dict) -> dict:
    """
    Scan for wide (>32 bit) declarations of any form:
        reg [N:0] name;
        wire [N:0] name;
        input wire [N:0] name;
        output reg [N:0] name;
        etc.
    Returns {signal_name: SignalLayout}
    """
    layouts = {}
    decl_re = re.compile(
        r'\b(?:(?:input|output|inout)\s+)?(?:reg|wire)?\s*\[(\d+):0\]\s+(\w+)\s*[;,)]'
    )
    for m in decl_re.finditer(text):
        hi       = int(m.group(1))
        total    = hi + 1
        sig_name = m.group(2)
        if total <= 32 or sig_name in layouts:
            continue
        if total in width_to_struct:
            struct_name = width_to_struct[total]
            layouts[sig_name] = SignalLayout(sig_name, structs[struct_name])
            print(f"    {sig_name}[{hi}:0] -> {struct_name} "
                  f"({', '.join(f for f, _ in structs[struct_name])})")
        else:
            print(f"    WARNING: {sig_name}[{hi}:0] ({total} bits) — "
                  f"no matching struct, skipping")
    return layouts


# ---------------------------------------------------------------------------
# Collect port->struct mapping from a module's port declarations
#
# sv2v emits the original wide port *names* in the module(...) header even
# after it expands them as separate input/output lines in the body.
# We need to know: for module `decode`, port `fbuf` corresponds to fbuf_data.
#
# We do this by scanning for input/output declarations whose name exactly
# matches a struct type name, or by recognising the pattern sv2v produces
# when it flattens a struct port: the port name becomes the *prefix* shared
# by a run of consecutive split fields.
# ---------------------------------------------------------------------------

def infer_port_structs(module_text: str, structs: dict) -> dict:
    """
    Returns {original_port_name: struct_name} for wide struct ports.

    Strategy: sv2v turns  `input fbuf_data fbuf`  into
        input wire [63:0] fbuf;   (in the port list / body)
    which we already handle via find_wide_signals / width matching.

    But it also sometimes just keeps the bare name `fbuf` in the port list
    header without a width annotation if the type info was lost.
    We detect this by looking at the port-body declarations that ARE annotated
    and building a prefix->struct map from them.
    """
    # Already handled by find_wide_signals for annotated declarations.
    # This function handles the case where the header has bare names only.
    # We'll build {prefix: struct_name} from known struct field sets.

    field_sets = {}
    for sname, fields in structs.items():
        field_sets[sname] = set(fname for fname, _ in fields)

    # Look for groups of consecutive input/output lines that share a prefix
    # matching a struct's field names.
    # e.g.:
    #   input wire [31:0] fbuf_pc_plus_1;
    #   input wire [31:0] fbuf_instruction;
    # -> prefix "fbuf" matches fbuf_data fields {pc_plus_1, instruction}

    decl_re = re.compile(
        r'(?:input|output)\s+(?:wire|reg)?\s*(?:\[\d+:\d+\]\s+)?(\w+)\s*;'
    )
    port_names = decl_re.findall(module_text)

    prefix_map = {}  # {prefix: {field_names found}}
    for pname in port_names:
        for sname, fields in structs.items():
            for fname, _ in fields:
                candidate_prefix = f"{pname[:-len(fname)-1]}" if pname.endswith(f"_{fname}") else None
                if candidate_prefix:
                    if candidate_prefix not in prefix_map:
                        prefix_map[candidate_prefix] = {}
                    if sname not in prefix_map[candidate_prefix]:
                        prefix_map[candidate_prefix][sname] = set()
                    prefix_map[candidate_prefix][sname].add(fname)

    result = {}
    for prefix, struct_hits in prefix_map.items():
        for sname, found_fields in struct_hits.items():
            all_fields = set(fname for fname, _ in structs[sname])
            if found_fields == all_fields:
                result[prefix] = sname

    return result  # {port_base_name: struct_name}


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------

def replace_port_list(text: str, layouts: dict) -> str:
    """
    Expand wide names in the `module foo(a, b, fbuf, dbuf, c);` header.
    """
    def replace_in_portlist(m):
        before = m.group(1)
        ports  = m.group(2)
        after  = m.group(3)

        new_ports = []
        for port in re.split(r',', ports):
            stripped = port.strip()
            if stripped in layouts:
                for (cname, _) in layouts[stripped].chunks:
                    new_ports.append(f"\n\t{cname}")
            else:
                new_ports.append(port)
        return before + ','.join(new_ports) + after

    port_list_re = re.compile(
        r'(module\s+\w+\s*\()' r'(.*?)' r'(\)\s*;)',
        re.DOTALL
    )
    return port_list_re.sub(replace_in_portlist, text)


def replace_declarations(text: str, layouts: dict) -> str:
    """Replace wide reg/wire/input/output declarations with per-field ones."""
    for sig, layout in layouts.items():
        total   = layout.total_bits
        pattern = re.compile(
            rf'(\s*)((?:(?:input|output|inout)\s+)?(?:reg|wire)?\s*)'
            rf'\[{total-1}:0\]\s+{re.escape(sig)}\s*;'
        )
        def replacer(m, layout_=layout):
            indent = m.group(1)
            prefix = m.group(2).rstrip()
            lines  = []
            for (cname, w) in layout_.chunks:
                width_str = f"[{w-1}:0] " if w > 1 else ""
                lines.append(f"{prefix} {width_str}{cname};")
            return '\n'.join(indent + l for l in lines)
        text = pattern.sub(replacer, text)
    return text


SLICE_RE = re.compile(r'\b(\w+)\[(\d+)(-:(\d+)|:(\d+))?\]')

def replace_slices(text: str, layouts: dict) -> str:
    def replacer(m):
        name = m.group(1)
        if name not in layouts:
            return m.group(0)
        layout = layouts[name]
        hi_str, rest = m.group(2), m.group(3)
        if rest is None:
            bit = int(hi_str)
            return layout.resolve_slice(bit, bit)
        elif m.group(4) is not None:
            hi = int(hi_str); w = int(m.group(4)); lo = hi - w + 1
        else:
            hi = int(hi_str); lo = int(m.group(5))
        return layout.resolve_slice(hi, lo)
    return SLICE_RE.sub(replacer, text)


def replace_instantiations(text: str, structs: dict,
                            all_port_structs: dict) -> str:
    """
    Rewrite module instantiation port connections.

    For a connection like  .fbuf(fbuf_out)  where:
      - 'fbuf' is a struct port on the target module  (lookup: all_port_structs[module_name]['fbuf'])
      - 'fbuf_out' is the signal connected to it in the parent

    We expand to:
      .fbuf_pc_plus_1(fbuf_out_pc_plus_1),
      .fbuf_instruction(fbuf_out_instruction)

    The key insight: the port fields are named  port_fieldname,
    so the connected signal's chunks are  connected_signal_fieldname.
    We just substitute the prefix.
    """

    # Match a full module instantiation:
    #   module_name inst_name ( ... );
    # We must NOT match keyword blocks like always/if/case.
    KEYWORDS = {'always', 'if', 'else', 'case', 'begin', 'end', 'assign',
                'initial', 'module', 'endmodule', 'localparam', 'parameter',
                'wire', 'reg', 'input', 'output', 'inout'}

    # Find instantiations manually using a paren-depth counter,
    # since  .*?  stops at the first ) inside the port list.
    # We scan for:   WORD  WORD  (  ...body...  )  ;
    header_re = re.compile(r'\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(')

    def expand_conn(port_name, connected_sig, port_structs):
        if port_name not in port_structs:
            return None
        struct_name = port_structs[port_name]
        fields      = structs[struct_name]
        pairs = []
        for (fname, _) in fields:
            pairs.append(f".{port_name}_{fname}({connected_sig}_{fname})")
        return ',\n\t\t'.join(pairs)

    result = []
    pos    = 0
    while pos < len(text):
        m = header_re.search(text, pos)
        if not m:
            result.append(text[pos:])
            break

        module_name = m.group(1)
        inst_name   = m.group(2)

        # Append everything up to the start of this match
        result.append(text[pos:m.start()])

        if module_name in KEYWORDS or inst_name in KEYWORDS:
            result.append(text[m.start():m.end()])
            pos = m.end()
            continue

        port_structs = all_port_structs.get(module_name, {})
        if not port_structs:
            result.append(text[m.start():m.end()])
            pos = m.end()
            continue

        # Walk forward counting parens to find the matching )
        depth     = 1
        i         = m.end()   # points just past the opening (
        body_start = i
        while i < len(text) and depth > 0:
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
            i += 1
        body     = text[body_start:i-1]   # between the outer ( and )
        after    = text[i:]

        # Check for trailing semicolon
        semi_m = re.match(r'\s*;', after)
        if not semi_m:
            # Not a proper instantiation (e.g. always @(...), case (...))
            # Only advance past the header match opening paren, NOT the whole
            # paren-balanced body — otherwise we skip over real instantiations.
            result.append(text[m.start():m.end()])
            pos = m.end()
            continue

        # Rewrite .port(signal) connections inside the body
        new_body = re.sub(
            r'\.(\w+)\((\w+)\)',
            lambda cm: expand_conn(cm.group(1), cm.group(2), port_structs) or cm.group(0),
            body
        )

        result.append(f"{module_name} {inst_name}({new_body}){semi_m.group(0)}")
        pos = i + len(semi_m.group(0))

    return ''.join(result)


def zero_val(width: int) -> str:
    return f"{width}'d0"


def make_chunked_latch(dst: SignalLayout, src: SignalLayout,
                       cond: str, indent: str) -> str:
    i = indent
    lines = [f"{i}always @(posedge clk) begin"]
    lines.append(f"{i}    if ({cond}) begin")
    for (cname, w) in dst.chunks:
        lines.append(f"{i}        {cname} <= {zero_val(w)};")
    lines.append(f"{i}    end else begin")
    for (dcname, _), (scname, _) in zip(dst.chunks, src.chunks):
        lines.append(f"{i}        {dcname} <= {scname};")
    lines.append(f"{i}    end")
    lines.append(f"{i}end")
    return '\n'.join(lines)


def make_chunked_latch_guarded(dst: SignalLayout, src: SignalLayout,
                                cond_reset: str, guard: str, indent: str) -> str:
    i = indent
    lines = [f"{i}always @(posedge clk) begin"]
    lines.append(f"{i}    if ({guard}) begin")
    lines.append(f"{i}        if ({cond_reset}) begin")
    for (cname, w) in dst.chunks:
        lines.append(f"{i}            {cname} <= {zero_val(w)};")
    lines.append(f"{i}        end else begin")
    for (dcname, _), (scname, _) in zip(dst.chunks, src.chunks):
        lines.append(f"{i}            {dcname} <= {scname};")
    lines.append(f"{i}        end")
    lines.append(f"{i}    end")
    lines.append(f"{i}end")
    return '\n'.join(lines)


def replace_latch_assignments(text: str, layouts: dict) -> str:
    for out_name, out_layout in layouts.items():
        if '_out' not in out_name:
            continue
        in_name = out_name.replace('_out', '_in')
        if in_name not in layouts:
            continue
        in_layout = layouts[in_name]
        total     = out_layout.total_bits

        # Guarded latch
        guarded_pat = re.compile(
            rf'(\s*)always @\(posedge clk\)\s*\n\s*'
            rf'if \(([^)]+)\)\s*\n\s*'
            rf'{re.escape(out_name)}\s*<=\s*\((.+?)\?\s*'
            rf'\{{{total}\s*\{{[^}}]*\}}}}\s*:\s*{re.escape(in_name)}\s*\)\s*;',
            re.MULTILINE | re.DOTALL
        )
        def guarded_repl(m, dl=out_layout, sl=in_layout):
            return make_chunked_latch_guarded(
                dl, sl,
                cond_reset=m.group(3).strip().rstrip('(').strip(),
                guard=m.group(2).strip(),
                indent=m.group(1)
            )
        text = guarded_pat.sub(guarded_repl, text)

        # Simple latch
        simple_pat = re.compile(
            rf'(\s*)always @\(posedge clk\)\s*'
            rf'{re.escape(out_name)}\s*<=\s*\((.+?)\?\s*'
            rf'\{{{total}\s*\{{[^}}]*\}}}}\s*:\s*{re.escape(in_name)}\s*\)\s*;',
            re.MULTILINE | re.DOTALL
        )
        def simple_repl(m, dl=out_layout, sl=in_layout):
            return make_chunked_latch(
                dl, sl,
                cond=m.group(2).strip().rstrip('?').strip(),
                indent=m.group(1)
            )
        text = simple_pat.sub(simple_repl, text)

    return text


# ---------------------------------------------------------------------------
# Split design.v into modules, process each independently
# ---------------------------------------------------------------------------

MODULE_SPLIT_RE = re.compile(r'(?=\bmodule\b)', re.MULTILINE)
MODULE_NAME_RE  = re.compile(r'\bmodule\s+(\w+)')


def split_modules(text: str):
    """Yield (module_name_or_None, chunk_text)."""
    for chunk in MODULE_SPLIT_RE.split(text):
        if not chunk.strip():
            continue
        nm = MODULE_NAME_RE.match(chunk.strip())
        yield (nm.group(1) if nm else None, chunk)


def process(design_text: str, types_text: str) -> str:
    print("Parsing types.sv...")
    enum_widths = parse_enum_widths(types_text)
    structs     = parse_structs(types_text, enum_widths)
    print(f"  Enums:   {list(enum_widths.keys())}")
    print(f"  Structs: {list(structs.keys())}")

    width_to_struct = {
        sum(w for _, w in fields): name
        for name, fields in structs.items()
    }

    modules = list(split_modules(design_text))

    # Pass 1: collect signal layouts and port->struct maps per module
    print("\nPass 1: Collecting layouts...")
    all_layouts      = {}   # {module_name: {sig_name: SignalLayout}}
    all_port_structs = {}   # {module_name: {port_base_name: struct_name}}

    for (name, text) in modules:
        if name is None:
            continue
        print(f"\n  Module: {name}")
        layouts      = find_wide_signals(text, width_to_struct, structs)
        port_structs = infer_port_structs(text, structs)
        
        # Merge the layouts discovered by width matching into port_structs.
        # This guarantees replace_instantiations knows about them.
        for sig, layout in layouts.items():
            if layout.total_bits in width_to_struct:
                port_structs[sig] = width_to_struct[layout.total_bits]

        all_layouts[name]      = layouts
        all_port_structs[name] = port_structs
        if port_structs:
            print(f"    Port structs: {port_structs}")

    # Pass 2: transform each module
    print("\nPass 2: Applying transformations...")
    result_parts = []
    for (name, mod_text) in modules:
        if name is None:
            result_parts.append(mod_text)
            continue

        layouts = all_layouts.get(name, {})
        print(f"\n  Module: {name}")

        if layouts:
            mod_text = replace_port_list(mod_text, layouts)
            mod_text = replace_declarations(mod_text, layouts)
            mod_text = replace_slices(mod_text, layouts)
            mod_text = replace_latch_assignments(mod_text, layouts)

        # Always attempt instantiation rewriting — parent module may not have
        # wide signals itself but still instantiate modules that do
        mod_text = replace_instantiations(mod_text, structs, all_port_structs)

        result_parts.append(mod_text)

    return ''.join(result_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Split wide sv2v buffer signals using struct layouts from types.sv"
    )
    parser.add_argument("input",   help="sv2v-generated .v file (rewritten in-place)")
    parser.add_argument("--types", default="types.sv",
                        help="Path to SystemVerilog types file (default: types.sv)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print result to stdout, don't overwrite")
    args = parser.parse_args()

    design_path = Path(args.input)
    types_path  = Path(args.types)

    for p in (design_path, types_path):
        if not p.exists():
            print(f"Error: {p} not found.", file=sys.stderr)
            sys.exit(1)

    design_text = design_path.read_text()
    types_text  = types_path.read_text()
    result      = process(design_text, types_text)

    if args.dry_run:
        print(result)
    else:
        backup = design_path.with_suffix(".v.bak")
        backup.write_text(design_text)
        design_path.write_text(result)
        print(f"\nDone. Original backed up to {backup}")


if __name__ == "__main__":
    main()
