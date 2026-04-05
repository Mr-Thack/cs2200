# --- Variables ---
TYPES = types.sv
SRC = pipeline.sv
COMPONENTS = alu.sv dprf.sv mem.sv
TB = test.sv
OUT = a.out
NETLIST = netlist.json

# --- Targets ---

all: test

# Compiles with SystemVerilog-2012 support and runs the simulation
test:
	@echo "--- Compiling Simulation ---"
	iverilog -g2012 -o $(OUT) $(TYPES) $(COMPONENTS) $(SRC) $(TB)
	@echo "--- Running Simulation ---"
	vvp $(OUT)
	@echo "--- Simulation Complete ---"
	@echo "--- Showing Simulation ---"
	gtkwave waves.vcd layout.gtkw 
	

# Runs Yosys to synthesize the pipeline into a JSON netlist
netlist:
	@echo "--- Synthesizing Netlist ---"
	yosys -p "read_verilog -sv $(TYPES) $(COMPONENTS) $(SRC); prep -top pipeline; write_json $(NETLIST)"
	@echo "--- Netlist Generated: $(NETLIST) ---"

# Opens the generated netlist in xdot for visual inspection
show: netlist
	@echo "--- Opening xdot ---"
	yosys -p "read_verilog -sv $(TYPES) $(COMPONENTS) $(SRC); prep -top pipeline; show"

# Cleans up generated files to keep your directory tidy
clean:
	@echo "--- Cleaning Workspace ---"
	rm -f $(OUT) $(NETLIST) *.vcd
