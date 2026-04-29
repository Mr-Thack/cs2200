#pragma once

/* Student checksum test cases, tests checksum in the length of even and odd buffer lengths. */
int student_checksum_test_cases(void);

/* Student packetize test cases, tests for when the packet length is not a multiple of `MAX_PAYLOAD_LENGTH` and when it is.*/
int student_packetize_test_cases(void);