#include "mmu.h"
#include "pagesim.h"
#include "swapops.h"
#include "stats.h"
#include "address_splitting.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

/**
 * ----------------- CHECKPOINT B: PAGE FAULT HANDLING -----------------
 * 
 * Page fault handler.
 * 
 * When the CPU encounters an invalid address mapping in a page table, it invokes the 
 * OS via this handler. Your job is to put a mapping in place so that the translation 
 * can succeed.
 * 
 * @param addr virtual address in the page that needs to be mapped into main memory.
 * 
 * HINTS:
 *      - You will need to use the global variable current_process when
 *      altering the frame table entry.
 *      - Use swap_exists() and swap_read() to update the data in the 
 *      frame as it is mapped in.
 * ---------------------------------------------------------------------
 */
void page_fault(vaddr_t address) {
    stats.page_faults++;

    vpn_t vpn = get_vaddr_vpn(address);

    pte_t *pte = get_page_table_entry(vpn, current_process->saved_ptbr, mem);

    pfn_t pfn = free_frame();

    if (swap_exists(pte)) {
        swap_read(pte, mem + (pfn * PAGE_SIZE));
    } else {
        // New mem, so zero it out
        for (int i = 0; i < PAGE_SIZE; i++) {
            mem[pfn * PAGE_SIZE + i] = 0;
        }
    }

    // Update Page Table
    pte->pfn = pfn;
    pte->valid = 1;
    pte->dirty = 0;

    // Update corresponding frame table entry
    fte_t *fte = &frame_table[pfn];
    fte->mapped = 1;
    fte->ref_count = 0;
    fte->process = current_process;
    fte->vpn = vpn;
}

#pragma GCC diagnostic pop
