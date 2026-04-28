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

PROGRAMS = pow fib TwoSum

# --- Default ---
.PHONY: stats 
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


# --- Stats Automation ---
stats: $(V_SRCS) $(IV_CELLS) $(TB)
	@echo "--- Compiling Simulation Environment ---"
	python generator.py
	@mkdir -p build
	@rm -f build/run_stats.txt
	@iverilog -g2012 -o build/stats.out $(IV_CELLS) $(V_SRCS) $(TB)
	@for prog in $(PROGRAMS); do \
		echo "======================="; \
		echo "      **$$prog**"; \
		vvp build/stats.out +MEM_FILE="../assembly/$$prog.hex" | grep -E "Cycles:|Instructions:|CPI:|TIMEOUT" > build/$$prog_stats.tmp; \
		cat build/$$prog_stats.tmp | tee -a build/run_stats.txt; \
		\
		CYCLES=$$(grep "Cycles:" build/$$prog_stats.tmp | awk '{print $$2}'); \
		\
		if [ "$$prog" = "pow" ]; then BASELINE=8129; \
		elif [ "$$prog" = "fib" ]; then BASELINE=32312; \
		elif [ "$$prog" = "TwoSum" ]; then BASELINE=12314; \
		else BASELINE=0; fi; \
		\
		if [ -n "$$CYCLES" ] && [ "$$BASELINE" -gt 0 ]; then \
			awk -v c="$$CYCLES" -v b="$$BASELINE" 'BEGIN { speedup=b/c; pct=(speedup-1)*100; printf "Speedup: %.2fx (+%.1f%%)\n", speedup, pct }'; \
		fi; \
		echo "======================="; \
		echo ""; \
	done
	@echo "======================="
	@echo "    OVERALL AVERAGE"
	@awk '/Cycles:/ {c+=$$2} /Instructions:/ {i+=$$2} END {if(i>0) printf "  Global CPI: %.5f\n", c/i}' build/run_stats.txt
	@awk 'BEGIN {b_tot=8129+32312+12314} /Cycles:/ {c+=$$2} END {if(c>0) { speedup=b_tot/c; pct=(speedup-1)*100; printf "Speedup: %.2fx (+%.1f%%)\n", speedup, pct }}' build/run_stats.txt
	@echo "======================="


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
