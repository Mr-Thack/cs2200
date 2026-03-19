#include "tests.h"
#include <string.h>


// TODO: remove after fixing warnings
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-prototypes"
#pragma GCC diagnostic ignored "-Wimplicit-function-declaration"

void _test_get_vaddr_vpn();
void _test_get_vaddr_offset();
void _test_get_page_table();
void _test_get_page_table_entry();
void _test_get_physical_address();

void run_tests() {
    test_get_vaddr_vpn(); 
    test_get_vaddr_offset();
    test_get_page_table();
    test_get_page_table_entry(); 
    test_get_physical_address();
    test_compute_stats();
    test_daemon_update();
    test_select_victim_frame_approx_lru();
    test_select_victim_frame_clocksweep(); 

    printf("All tests passed!\n");
}

int run_select_test(const char *test_name) {
    if (test_name == NULL) {
        return -1;
    }

    // Verify address splitting tests are working correctly before running the rest of the tests, since the rest of the tests depend on those functions working correctly.
    if (strcmp(test_name, "get_vaddr_vpn") == 0) {
        test_get_vaddr_vpn();
        return 0;
    } else if (strcmp(test_name, "get_vaddr_offset") == 0) {
        test_get_vaddr_offset();
        return 0;
    } else if (strcmp(test_name, "get_page_table") == 0) {
        test_get_page_table();
        return 0;
    } else if (strcmp(test_name, "get_page_table_entry") == 0) {
        test_get_page_table_entry();
        return 0;
    } else if (strcmp(test_name, "get_physical_address") == 0) {
        test_get_physical_address();
        return 0;
    } else {
        _test_get_vaddr_vpn();
        _test_get_vaddr_offset();
        _test_get_page_table();
        _test_get_page_table_entry();
        _test_get_physical_address();
    }

    if (strcmp(test_name, "compute_stats") == 0) {
        test_compute_stats();
    } else if (strcmp(test_name, "daemon_update") == 0) {
        test_daemon_update();
    } else if (strcmp(test_name, "select_victim_frame_approx_lru") == 0) {
        test_select_victim_frame_approx_lru();
    } else if (strcmp(test_name, "select_victim_frame_clocksweep") == 0) {
        test_select_victim_frame_clocksweep();
    } else {
        return -1; // Unknown test
    }
    return 0;
}

void _test_get_vaddr_vpn() {
    assert(get_vaddr_vpn((vaddr_t) ((0xFF<<OFFSET_LEN) + 0x2032)) == 0xFF);
}

void test_get_vaddr_vpn() {
    _test_get_vaddr_vpn();
    printf("Passed address_splitting.h/get_vaddr_vpn() test!\n");
}

void _test_get_vaddr_offset() {
    assert(get_vaddr_offset((vaddr_t) ((0xFF<<OFFSET_LEN) + 0x2032)) == 0x2032);
}

void test_get_vaddr_offset() {
    _test_get_vaddr_offset();
    printf("Passed address_splitting.h/get_vaddr_offset() test!\n");
}

void _test_get_page_table() {
    pte_t* page_table = get_page_table(0x3, 0x00);
    assert(page_table == (pte_t*) 0xc000);
}

void test_get_page_table() {
    _test_get_page_table();
    printf("Passed address_splitting.h/get_page_table() test!\n");
}

void _test_get_page_table_entry() {
    pte_t* page_table_entry = get_page_table_entry(0x1, 0x3, 0x00);
    assert(page_table_entry == (pte_t*)0xc010);
}

void test_get_page_table_entry() {
    _test_get_page_table_entry();
    printf("Passed address_splitting.h/get_page_table_entry() test!\n");
}

void _test_get_physical_address() {
    assert(get_physical_address(0x3, 0x2032) == 0xe032);
}

void test_get_physical_address() {
   _test_get_physical_address();
   printf("Passed address_splitting.h/get_physical_address() test!\n");
}

void test_compute_stats() {
    stats.accesses = 21;
    stats.writebacks = 5;
    stats.page_faults = 3;

    compute_stats();

    // casting to int to avoid floating point comparison, should be fine for this case
    assert((int)stats.amat == (int)81152);
    printf("Passed stats.c/compute_stats() test!\n");

}

void test_daemon_update() {
    // Make sure your get_page_table_entry() function is working correctly, otherwise this test will fail.

    // Initialization
    mem = calloc(1, MEM_SIZE);
    pcb_t* process = (pcb_t*) malloc(sizeof(pcb_t));
    process->pid = 0;
    process->state = PROC_RUNNING;
    process->saved_ptbr = 0x2; // TODO: verify this is correct


    frame_table = (fte_t*) mem;

    int i = 1;

    frame_table[i].process = process;
    frame_table[i].vpn = 0x10;
    frame_table[i].ref_count = 0;

    // TODO: are these bits being set correctly?
    frame_table[i].mapped = 1;
    frame_table[i].protected = 0;

    pte_t* page_table_entry = get_page_table_entry(frame_table[i].vpn, frame_table[i].process->saved_ptbr, mem);

    // Testing your code.
    page_table_entry->referenced = 1;
    daemon_update();
    assert(frame_table[1].ref_count == 128);
    page_table_entry->referenced = 1;
    daemon_update();
    assert(frame_table[1].ref_count == 192);
    daemon_update();
    assert(frame_table[1].ref_count == 96);


    // cleanup
    free(mem);
    free(process);

    printf("Passed page_replacement.c/daemon_update() test!\n");
}

void test_select_victim_frame_approx_lru() {

    mem = calloc(1, MEM_SIZE);
    frame_table = (fte_t*) mem;


    // make all the pages in memory mapped.
    for (int i = 0; i < NUM_FRAMES; i++) {
        frame_table[i].protected = 0;
        frame_table[i].mapped = 1;
        frame_table[i].ref_count = 0xFF;
    }

    // protect the frame table
    frame_table[0].protected = 1;

    frame_table[1].ref_count = 192;
    frame_table[2].ref_count = 128;
    frame_table[3].ref_count = 245;

    replacement = APPROX_LRU;

    assert(select_victim_frame() == 2);

    free(mem);

    printf("Passed page_replacement.c/select_victim_frame() - approx_lru test!\n");
}

void test_select_victim_frame_clocksweep() {

    mem = calloc(1, MEM_SIZE);
    frame_table = (fte_t*) mem;

    pcb_t* process = (pcb_t*) malloc(sizeof(pcb_t));
    process->pid = 0;
    process->state = PROC_RUNNING;
    process->saved_ptbr = 0x2; // TODO: verify this is correct


    // make all the pages in memory mapped.
    for (int i = 1; i < NUM_FRAMES; i++) {
        frame_table[i].protected = 0;
        frame_table[i].mapped = 1;
    }

    for (int i = 1; i < 4; i++) {
        frame_table[i].process = process;
        frame_table[i].vpn = i;

    }


    // protect the frame table
    frame_table[0].protected = 1;
    frame_table[1].mapped = 1;

    replacement = CLOCKSWEEP;

    last_evicted = 0;
    pte_t* page_table_entry_1 = get_page_table_entry(1, process->saved_ptbr, mem);
    pte_t* page_table_entry_2 = get_page_table_entry(2, process->saved_ptbr, mem);
    pte_t* page_table_entry_3 = get_page_table_entry(3, process->saved_ptbr, mem);

    page_table_entry_1->referenced = 1;
    page_table_entry_2->referenced = 1;
    page_table_entry_3->referenced = 0;

    assert(select_victim_frame() == 3);
    
    // Last evicted would never be reset like this in the actual implementation, but we are doing it for testing purposes, so we can test an edge case.
    last_evicted = 0;
    assert(select_victim_frame() == 1);

    free(mem);
    free(process);

    printf("Passed page_replacement.c/select_victim_frame() - Second Chance (Clock Sweep) test!\n");
}
