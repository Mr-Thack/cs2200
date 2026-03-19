# Authored by Christopher Tam for Georgia Tech's CS 2200; Modified for vmem packaging
TARGET = vm-sim
TARGET_AG = vm-sim-ag

CC     = gcc
CFLAGS = -Wall -Wextra -Wsign-conversion -Wpointer-arith -Wcast-qual -Wwrite-strings -Wshadow -Wmissing-prototypes -Wpedantic -Wwrite-strings -g -std=gnu99 -lm
LFLAGS =
BINDIR = .

ifneq ($(wildcard simulator-src),)
SRC_BASE :=
else ifneq ($(wildcard src/simulator-src),)
SRC_BASE := src/
else
$(error Could not find simulator-src in current directory or src/)
endif

SIM_DIR := $(SRC_BASE)simulator-src
STUDENT_DIR := $(SRC_BASE)student-src
SOLUTION_DIR := $(SRC_BASE)solution-src
AUTOGRADER_DIR := $(SRC_BASE)autograder-src

IMPL_DIR := $(firstword $(wildcard $(STUDENT_DIR) $(SOLUTION_DIR)))
ifeq ($(IMPL_DIR),)
$(error Could not find student-src or solution-src)
endif

ifeq ($(AUTOGRADER),1)
AG_IMPL_DIR := $(firstword $(wildcard $(SOLUTION_DIR) $(STUDENT_DIR)))
SRCDIRS := $(SIM_DIR) $(AG_IMPL_DIR)
ifneq ($(wildcard $(AUTOGRADER_DIR)),)
SRCDIRS += $(AUTOGRADER_DIR)
endif
else
SRCDIRS := $(SIM_DIR) $(IMPL_DIR)
endif

SRC := $(foreach d,$(SRCDIRS),$(wildcard $(d)/*.c))
INC := $(foreach d,$(SRCDIRS),$(wildcard $(d)/*.h))

INCFLAGS := $(foreach d,$(SRCDIRS),-I$(d))

SUBMIT_FILES  = $(SRC) $(INC) Makefile
SUBMISSION_NAME = project3-vm

.PHONY: all
all:
	@$(MAKE) release

.PHONY: debug
debug: CFLAGS += -ggdb -g3 -DDEBUG
debug: $(BINDIR)/$(TARGET)

.PHONY: release
release: CFLAGS += -mtune=native -O2
release: $(BINDIR)/$(TARGET)

.PHONY: autograder
autograder:
	@$(MAKE) clean
	@$(MAKE) $(BINDIR)/$(TARGET_AG) AUTOGRADER=1 CFLAGS="$(CFLAGS) -DAUTOGRADER"

.PHONY: clean
clean:
	@rm -f $(BINDIR)/$(TARGET)
	@rm -f $(BINDIR)/$(TARGET_AG)
	@rm -rf $(BINDIR)/$(TARGET).dSYM
	@rm -rf $(BINDIR)/$(TARGET_AG).dSYM

.PHONY: submit
submit:
	@(tar zcfh $(SUBMISSION_NAME).tar.gz $(SUBMIT_FILES) && \
	echo "Created submission archive $$(tput bold)$(SUBMISSION_NAME).tar.gz$$(tput sgr0).")

$(BINDIR)/$(TARGET): $(SRC) $(INC)
	@mkdir -p $(BINDIR)
	@$(CC) $(CFLAGS) $(INCFLAGS) $(SRC) -o $@ $(LFLAGS)

$(BINDIR)/$(TARGET_AG): $(SRC) $(INC)
	@mkdir -p $(BINDIR)
	@$(CC) $(CFLAGS) $(INCFLAGS) $(SRC) -o $@ $(LFLAGS)
