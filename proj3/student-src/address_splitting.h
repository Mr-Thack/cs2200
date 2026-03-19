#pragma once

#include "mmu.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

/**
 * ------------------- CHECKPOINT A: ADDRESS SPLITTING -------------------
 *
 * Implement helper functions used to split virtual addresses and compute
 * page-table / physical-memory locations.
 * 
 * HINT: 
 *      - Examine the global defines in pagesim.h, which are necessary when
 *      implementing these functions.
 * ----------------------------------------------------------------------
 */

static inline vpn_t get_vaddr_vpn(vaddr_t addr) {
    return (vpn_t) (addr >> OFFSET_LEN); 
}

static inline uint16_t get_vaddr_offset(vaddr_t addr) {
    return addr % PAGE_SIZE; 
}

static inline pte_t* get_page_table(pfn_t ptbr, uint8_t *memory) {
    return (pte_t*) &memory[ptbr * PAGE_SIZE];
}

static inline pte_t* get_page_table_entry(vpn_t vpn, pfn_t ptbr, uint8_t *memory) {
    return &get_page_table(ptbr, memory)[vpn];
}

static inline paddr_t get_physical_address(pfn_t pfn, uint16_t offset) {
    return (((paddr_t) pfn) << OFFSET_LEN) + ((paddr_t) offset);
}

#pragma GCC diagnostic pop
