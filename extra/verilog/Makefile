# --- Variables ---
TYPES = types.sv
SRC = pipeline.sv
COMPONENTS = btb.sv ras.sv dprf.sv fusion.sv fetch.sv decode.sv alu.sv cmp.sv log.sv execute.sv
TB = test.sv

CS_CELLS = ccellscs.sv 
IV_CELLS = ccellsiv.sv

# Universal
SV_SRCS = $(TYPES) $(COMPONENTS) $(SRC)
V_SRCS = build/design.v

TOP = Datapath

OUT = build/a.out
NETLIST = build/netlist.json
SIM = build/cpu.sim

# --- Default ---
.PHONY: all test runtest netlist sim runsim clean verilog
all: test

$(V_SRCS): $(SV_SRCS) $(TYPES)
	@echo "--- Converting Core SystemVerilog to Verilog ---"
	mkdir -p build
	sv2v $(SV_SRCS) -w $(V_SRCS)
	python split_wide.py $(V_SRCS) --types $(TYPES)

# Just an alias
verilog: $(V_SRCS)

# --- Simulation ---
test: $(V_SRCS) $(IV_CELLS) $(TB)
	@echo "--- Compiling Simulation ---"
	python generator.py
	iverilog -g2012 -o $(OUT) $(IV_CELLS) $(V_SRCS) $(TB)
	@echo "--- Running Simulation ---"
	vvp $(OUT)

runtest: test
	@echo "--- Opening GTKWave ---"
	gtkwave ./build/waves.vcd layout.gtkw


# --- Synthesis ---
YOSYS_PASSES = \
	read_verilog -sv $(CS_CELLS) $(V_SRCS) $(TOP).sv; \
	prep -top $(TOP); \
	wreduce; opt_expr; opt_merge; opt_muxtree; \
	share; opt -full; clean -purge; \
	write_json $(NETLIST)

# --- Step 2: Yosys synthesis ---
netlist: $(V_SRCS) $(CS_CELLS) $(TOP).sv
	@echo "--- Synthesizing Netlist ---"
	yosys -p "$(YOSYS_PASSES)"
	@echo "--- Netlist Generated ---"

# --- Step 3: CircuitSim generation ---
sim: netlist
	@echo "--- Generating CircuitSim file ---"
	python compiler.py $(NETLIST) $(SIM)

runsim: sim
	@echo "--- Opening CircuitSim ---"
	CircuitSim $(SIM)

# --- Cleanup ---
clean:
	rm -rf build $(OUT) *.vcd $(SIM)
