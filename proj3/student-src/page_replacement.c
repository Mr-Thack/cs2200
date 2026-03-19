#include "types.h"
#include "pagesim.h"
#include "mmu.h"
#include "swapops.h"
#include "stats.h"
#include "util.h"

pfn_t select_victim_frame(void);

pfn_t last_evicted = 0;

/**
 * --------- CHECKPOINT A: FREE FRAME SELECTION AND EVICTION ---------
 *
 * Make a free frame for the system to use. You call the select_victim_frame() method
 * to identify an "available" frame in the system (already given). You will need to
 * check to see if this frame is already mapped in, and if it is, you need to evict it.
 *
 * @return victim_pfn: a physical frame number to a free frame used by other functions.
 *
 * HINTS:
 *      - When evicting pages, remember what you checked for to trigger page faults
 *      in mem_access
 *      - If the page table entry has been written to before, you will need to use
 *      swap_write() to save the contents to the swap queue.
 * -------------------------------------------------------------------
 */
pfn_t free_frame(void) {
    pfn_t pfn = select_victim_frame();
    fte_t* victim = &frame_table[pfn];

    if (victim->mapped) {
        pte_t* pte = get_page_table_entry(victim->vpn, victim->process->saved_ptbr, mem);
        if (pte->dirty) {
            swap_write(pte, mem + pfn * PAGE_SIZE);
            stats.writebacks++;
            pte->dirty = 0;
        }
        pte->valid = 0;
        victim->mapped = 0;
    }

    return pfn;
}

/**
 * ---------------- CHECKPOINT A: BETTER VICTIM SELECTION ----------------
 *
 * Finds a free physical frame. If none are available, uses either a
 * randomized, FCFS, or Second Chance (Clock Sweep) algorithm to find a used frame for
 * eviction.
 *
 * @return The physical frame number of a victim frame.
 *
 * HINTS:
 *      - Use the global variables MEM_SIZE and PAGE_SIZE to calculate
 *      the number of entries in the frame table.
 *      - Use the global last_evicted to keep track of the pointer into the frame table
 * ----------------------------------------------------------------------
 */
pfn_t select_victim_frame()
{
    /* See if there are any free frames first */
    size_t num_entries = MEM_SIZE / PAGE_SIZE;
    for (size_t i = 0; i < num_entries; i++)
    {
        if (!frame_table[i].protected && !frame_table[i].mapped)
        {
            return i;
        }
    }

    if (replacement == RANDOM)
    {
        /* Play Russian Roulette to decide which frame to evict */
        pfn_t unprotected_found = NUM_FRAMES;
        for (pfn_t i = 0; i < num_entries; i++)
        {
            if (!frame_table[i].protected)
            {
                unprotected_found = i;
                if (prng_rand() % 2)
                {
                    return i;
                }
            }
        }
        /* If no victim found yet take the last unprotected frame
           seen */
        if (unprotected_found < NUM_FRAMES)
        {
            return unprotected_found;
        }
    }
    else if (replacement == APPROX_LRU)
    {
        pfn_t victim = 0;
        uint8_t min_refs;
        // Starting from 1 because recall that 0 is already reserved for frame_table
        for (size_t i = 1; i < num_entries; i++)
        {
            if (!frame_table[i].protected && (!victim || frame_table[i].ref_count < min_refs))
            {
                min_refs = frame_table[i].ref_count;
                victim = i;
            }
        }
        return victim;
    }
    else if (replacement == CLOCKSWEEP)
    {
        pfn_t victim_pfn = last_evicted;
        fte_t* victim;
        pte_t* pte;

        while (1) {
            victim = &frame_table[victim_pfn];

            if (!victim->protected) {
                pte = get_page_table_entry(victim->vpn, victim->process->saved_ptbr, mem);
                if (pte->referenced) {
                    pte->referenced = 0;
                } else {
                    last_evicted = victim_pfn;
                    return victim_pfn;
                }
            }
            victim_pfn = (victim_pfn + 1) % num_entries;
        }
    }

    // If every frame is protected, give up. This should never happen on the traces we provide you.
    panic("System ran out of memory\n");
    exit(1);
}
/**
 * ------------- CHECKPOINT B: DAEMON UPDATES FOR APPROXIMATE LRU -------------
 *
 * Updates the associated variables for the Approximate LRU,
 * called every time the simulator daemon wakes up.
 *
 * -------------------------------------------------------------------------------
 */
void daemon_update(void)
{
    /* FIX ME */
}
