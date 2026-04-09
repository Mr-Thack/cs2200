import re, sys

text = open('build/design.v').read()

# Simulate exactly what the walker does for decode dec(
pos = text.find('decode dec(')
header_re = re.compile(r'\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(')
m = header_re.search(text, pos)
print('module_name:', repr(m.group(1)))
print('inst_name:', repr(m.group(2)))

# Walk parens
depth = 1
i = m.end()
body_start = i
while i < len(text) and depth > 0:
    if text[i] == '(':
        depth += 1
    elif text[i] == ')':
        depth -= 1
    i += 1
body = text[body_start:i-1]
print('body:', repr(body))

after = text[i:]
semi_m = re.match(r'\s*;', after)
print('semi found:', bool(semi_m))

# Simulate the port_structs check
all_port_structs = {'decode': {'fbuf': 'fbuf_data', 'dbuf': 'dbuf_data'}}
port_structs = all_port_structs.get('decode', {})
print('port_structs:', port_structs)
print()

# Simulate replace_conn
for cm in re.finditer(r'\.(\w+)\((\w+)\)', body):
    print(f'  conn: port={cm.group(1)!r} sig={cm.group(2)!r}  -> in port_structs: {cm.group(1) in port_structs}')
