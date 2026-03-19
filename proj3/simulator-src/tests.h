/*
 * tests.h
 * Header file for test functions.
 */

#pragma once

#include <stdio.h>
#include <assert.h> 
#include <stdlib.h>
#include "address_splitting.h"
#include "stats.h"

void run_tests();
int run_select_test(const char *test_name);

void test_get_vaddr_vpn();
void test_get_vaddr_offset();
void test_get_page_table();
void test_get_page_table_entry();
void test_get_physical_address();
void test_compute_stats();
void test_select_victim_frame_approx_lru();
void test_select_victim_frame_clocksweep();
void test_daemon_update();

