# --- Variables ---
TYPES = types.sv
SRC = pipeline.sv
COMPONENTS = alu.sv dprf.sv mem.sv
TB = test.sv

SV_SRCS = $(TYPES) $(COMPONENTS) $(SRC)
V_SRCS = build/design.v

OUT = build/a.out
NETLIST = build/netlist.json
SIM = build/cpu.sim

# --- Default ---
all: test

# --- Step 1: Convert SV → Verilog ---
verilog:
	@echo "--- Converting SystemVerilog to Verilog ---"
	mkdir -p build
	sv2v $(SV_SRCS) -w $(V_SRCS)
	python split_wide.py $(V_SRCS) --types $(TYPES)

# --- Simulation (SystemVerilog directly) ---
test: verilog
	@echo "--- Compiling Simulation ---"
	iverilog -g2012 -o $(OUT) $(V_SRCS) $(TB)
	@echo "--- Running Simulation ---"
	vvp $(OUT)
	@echo "--- Opening GTKWave ---"
	gtkwave ./build/waves.vcd layout.gtkw


# --- Step 2: Yosys synthesis ---
netlist: verilog
	@echo "--- Synthesizing Netlist ---"
	yosys -p "read_verilog $(V_SRCS); prep -top pipeline; write_json $(NETLIST)"
	@echo "--- Netlist Generated ---"

# --- Step 3: CircuitSim generation ---
sim: netlist
	@echo "--- Generating CircuitSim file ---"
	python compiler.py $(NETLIST) $(SIM)
	@echo "--- Opening CircuitSim ---"
	CircuitSim $(SIM)

# --- Debug graph (optional) ---
show: verilog
	yosys -p "read_verilog $(V_SRCS); prep -top pipeline; show -prefix build/graph"

# --- Cleanup ---
clean:
	rm -rf build $(OUT) *.vcd $(SIM)
