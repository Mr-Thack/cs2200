#!/usr/bin/env python3
"""
split_wide.py

Splits wide pipeline buffer signals in sv2v-generated Verilog by reading
struct definitions directly from a SystemVerilog types file.

Instead of splitting into arbitrary 32-bit chunks (w0, w1, w2...),
it splits on FIELD BOUNDARIES, giving you named signals like:
    dbuf_out_pc_plus_1, dbuf_out_opcode, dbuf_out_val1, ...

This matches what you'd get if you'd manually unrolled the struct,
and is much more readable in your EDA tool.

Usage:
    python split_wide.py build/design.v --types types.sv [--dry-run]
"""

import re
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Step 0: Parse types.sv to extract struct field layouts
# ---------------------------------------------------------------------------

def parse_enum_widths(sv_text: str) -> dict:
    """Return {enum_type_name: bit_width} for all typedef enums."""
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
    Return {struct_type_name: [(field_name, bit_width), ...]}
    Fields are in MSB-first (declaration) order, matching sv2v packing.
    Handles logic [N:0], plain logic, enum types, and nested packed structs.
    """
    structs = {}

    for sm in re.finditer(
        r'typedef\s+struct\s+packed\s*\{([^}]*)\}\s*(\w+)\s*;',
        sv_text,
        re.DOTALL
    ):
        body = sm.group(1)
        struct_name = sm.group(2)
        fields = []

        for line in body.strip().splitlines():
            line = line.strip().rstrip(';').strip()
            if not line or line.startswith('//'):
                continue

            # logic [N:M] field_name
            m = re.match(r'logic\s+\[(\d+):(\d+)\]\s+(\w+)', line)
            if m:
                hi, lo, fname = int(m.group(1)), int(m.group(2)), m.group(3)
                fields.append((fname, hi - lo + 1))
                continue

            # logic field_name  (1-bit)
            m = re.match(r'logic\s+(\w+)', line)
            if m:
                fields.append((m.group(1), 1))
                continue

            # some_type field_name  (enum or nested struct)
            m = re.match(r'(\w+)\s+(\w+)', line)
            if m:
                type_name, fname = m.group(1), m.group(2)
                if type_name in enum_widths:
                    fields.append((fname, enum_widths[type_name]))
                elif type_name in structs:
                    total = sum(w for _, w in structs[type_name])
                    fields.append((fname, total))
                else:
                    print(f"  WARNING: unknown type '{type_name}' for field "
                          f"'{fname}' in {struct_name}, skipping")
                continue

        structs[struct_name] = fields

    return structs


# ---------------------------------------------------------------------------
# Signal layout: maps a wide signal to its named field chunks
# ---------------------------------------------------------------------------

class SignalLayout:
    """
    Represents a wide signal and its field decomposition.
    Chunks are field-aligned, named, and in MSB-first order.
    e.g. dbuf_out -> [dbuf_out_pc_plus_1[31:0], dbuf_out_opcode[3:0], ...]
    """
    def __init__(self, signal_name: str, fields: list):
        self.name = signal_name
        self.fields = fields
        self.total_bits = sum(w for _, w in fields)
        self.chunks = [(f"{signal_name}_{fname}", w) for fname, w in fields]

        # Absolute bit ranges for each chunk, MSB-first
        self.chunk_ranges = []
        cursor = self.total_bits - 1
        for (cname, w) in self.chunks:
            self.chunk_ranges.append((cname, cursor, cursor - w + 1, w))
            cursor -= w

    def resolve_slice(self, hi: int, lo: int) -> str:
        """Return a Verilog expression for absolute bits [hi:lo]."""
        parts = []
        for (cname, chi, clo, cw) in self.chunk_ranges:
            overlap_hi = min(hi, chi)
            overlap_lo = max(lo, clo)
            if overlap_hi < overlap_lo:
                continue
            local_hi = overlap_hi - clo
            local_lo = overlap_lo - clo
            if local_hi == local_lo:
                parts.append(f"{cname}[{local_hi}]")
            elif local_hi == cw - 1 and local_lo == 0:
                parts.append(cname)
            else:
                parts.append(f"{cname}[{local_hi}:{local_lo}]")
        if not parts:
            raise ValueError(f"Empty slice [{hi}:{lo}] on {self.name}")
        return parts[0] if len(parts) == 1 else '{' + ', '.join(parts) + '}'


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------

def replace_declarations(text: str, layouts: dict) -> str:
    for sig, layout in layouts.items():
        total = layout.total_bits
        pattern = re.compile(
                rf'(\s*)(reg|wire)\s+\[{total-1}:0\]\s+{re.escape(sig)}\s*;'
                )
        def replacer(m, layout_=layout):
            indent = m.group(1)
            kind = m.group(2)
            lines = [
                f"{kind} [{w-1}:0] {cname};" if w > 1 else f"{kind} {cname};"
                for (cname, w) in layout_.chunks
            ]
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
    """
    Replace wide always_ff latch patterns for all *_out signals.
    Handles:
        - always @(posedge clk) sig_out <= (COND ? {N{...}} : sig_in);
      - always @(posedge clk)\n  if (GUARD)\n    sig_out <= (COND ? {N{...}} : sig_in);
    """
    for out_name, out_layout in layouts.items():
        if '_out' not in out_name:
            continue
        in_name = out_name.replace('_out', '_in')
        if in_name not in layouts:
            continue
        in_layout = layouts[in_name]
        total = out_layout.total_bits

        # Pattern: guarded latch (e.g. fbuf with !halt_now && !stall_now)
        guarded_pat = re.compile(
                rf'(\s*)always @\(posedge clk\)\s*\n\s*'
                rf'if \(([^)]+)\)\s*\n\s*'
        rf'{re.escape(out_name)}\s*<=\s*\((.+?)\?\s*\{{{total}\s*\{{[^}}]*\}}}}\s*:\s*{re.escape(in_name)}\s*\)\s*;',
            re.MULTILINE | re.DOTALL
        )
        
        def guarded_repl(m, dl=out_layout, sl=in_layout):
            guard = m.group(2).strip()
            cond  = m.group(3).strip().rstrip('(').strip()
            return make_chunked_latch_guarded(dl, sl, cond, guard, m.group(1))
          
        text = guarded_pat.sub(guarded_repl, text)

        # Pattern: simple latch
        simple_pat = re.compile(
            rf'(\s*)always @\(posedge clk\)\s*'
            rf'{re.escape(out_name)}\s*<=\s*\((.+?)\?\s*\{{{total}\s*\{{[^}}]*\}}}}\s*:\s*{re.escape(in_name)}\s*\)\s*;',
            re.MULTILINE | re.DOTALL
        )

        def simple_repl(m, dl=out_layout, sl=in_layout):
            cond = m.group(2).strip().rstrip('?').strip()
            return make_chunked_latch(dl, sl, cond, m.group(1))

        text = simple_pat.sub(simple_repl, text)

    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process(design_text: str, types_text: str) -> str:
    print("Parsing types.sv...")
    enum_widths = parse_enum_widths(types_text)
    structs     = parse_structs(types_text, enum_widths)
    print(f"  Enums:   {list(enum_widths.keys())}")
    print(f"  Structs: {list(structs.keys())}")

    # Map total_bits -> struct_name for matching wide signals
    width_to_struct = {
        sum(w for _, w in fields): name
        for name, fields in structs.items()
    }

    # Find all wide (>32 bit) reg/wire declarations in design.v
    layouts = {}
    for m in re.finditer(r'(reg|wire)\s+\[(\d+):0\]\s+(\w+)\s*;', design_text):
        hi = int(m.group(2))
        total = hi + 1
        sig_name = m.group(3)
        if total <= 32:
            continue
        if total in width_to_struct:
            struct_name = width_to_struct[total]
            layouts[sig_name] = SignalLayout(sig_name, structs[struct_name])
            print(f"  {sig_name}[{hi}:0]  ->  {struct_name}  "
                  f"({', '.join(f for f,_ in structs[struct_name])})")
        else:
            print(f"  WARNING: {sig_name}[{hi}:0] ({total} bits) has no "
                  f"matching struct — skipping")

    if not layouts:
        print("No wide signals found. Nothing to do.")
        return design_text

    print("\nStep 1: Replacing wide declarations with named field signals...")
    design_text = replace_declarations(design_text, layouts)

    print("Step 2: Replacing bit-slice references...")
    design_text = replace_slices(design_text, layouts)

    print("Step 3: Replacing wide latch assignments...")
    design_text = replace_latch_assignments(design_text, layouts)

    return design_text


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
            print(f"Error: {p} not found.", file=sys.stderr); sys.exit(1)

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
