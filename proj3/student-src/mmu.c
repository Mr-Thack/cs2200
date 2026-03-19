#include "mmu.h"
#include "pagesim.h"
#include "address_splitting.h"
#include "swapops.h"
#include "stats.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

/* The frame table pointer. You will set this up in system_init. */
fte_t *frame_table;

/**
 * ---------------- CHECKPOINT A: SYSTEM INITIALIZATION ----------------
 * 
 * In this problem, you will initialize the frame_table pointer. The frame table will
 * be located at physical address 0 in our simulated memory. You should zero out the 
 * entries in the frame table, in case for any reason physical memory is not clean.
 * 
 * HINTS:
 *      - mem: Simulated physical memory already allocated for you.
 *      - PAGE_SIZE: The size of one page
 * --------------------------------------------------------------------
 */
void system_init(void) {
    frame_table = (fte_t*) mem;
    
    for (int i = 0; i < NUM_FRAMES; i++) {
        frame_table[i].protected = 0;
        frame_table[i].mapped = 0;
        frame_table[i].ref_count = 0;
        frame_table[i].process = NULL;
        frame_table[i].vpn = 0;
    }

    frame_table[0].protected = 1; 
}


/**
 * --------------- CHECKPOINT B: READING AND WRITING MEMORY ---------------
 * 
 * Takes an input virtual address and performs a memory operation.
 * 
 * @param addr virtual address to be translated
 * @param access   'r' if the access is a read, 'w' if a write
 * @param data If the access is a write, one byte of data to write to our memory.
 *             Otherwise NULL for read accesses.
 * 
 * HINTS:
 *      - Remember that not all the entry in the process's page table are mapped in. 
 *      Check what in the pte_t struct signals that the entry is mapped in memory.
 * -----------------------------------------------------------------------
 */
uint8_t mem_access(vaddr_t address, char access, uint8_t data) {
    return 0;
}
