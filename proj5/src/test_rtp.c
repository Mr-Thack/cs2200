#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "network.h"
#include "rtp.h"
#include "test_rtp.h"

int student_checksum_test_cases(void) {
    // length is even
    {
        char test1[] = "ABCD";
        int csum = checksum(test1, 4);
        
        if (csum != 402) {
            printf("Checksum of \"%s\" was %d, expected it to be 402 \n", test1, csum);
        } else {
            printf("Checksum test1 passed! \n");
        }
    }

    // length is odd
    {
        char test2[] = "abcdefg";
        int csum = checksum(test2, 7);

        if (csum != 2125) {
            printf("Checksum of \"%s\" was %d, expected it to be 2125 \n", test2, csum);
        } else {
            printf("Checksum test2 passed! \n");
        }
    }

    return 0;
}

int student_packetize_test_cases(void) {
    // length % MAX_PAYLOAD_LENGTH != 0
    {
        char test2[] = "Hello, this is a test to see how packetize splits me!";
        int length = strlen(test2);
        int count = 0;
        int succeeded = 1;

        packet_t *packets = packetize(test2, length, &count);

        if (count != 6) {
            succeeded = 0;
            printf("Number of packets was %d, expected to be %d\n", count, 6);
            goto clean_up_p1_test_case; // This line jumps to `clean_up_p1_test_case` so the code below doesn't execute
        }

        int checksums[] = {4039, 3957, 3739, 4551, 4162, 208};
        int lengths[] = {10, 10, 10, 10, 10, 3};
        char *payloads[] = {"Hello, thi", "s is a tes", "t to see h", "ow packeti", "ze splits ", "me!"};
        for (int i = 0; i < 5; i++) {
            if (packets[i].checksum != checksums[i]) {
                printf("Packet %d: actual checksum: %d, expected checksum: %d \n", i, packets[i].checksum, checksums[i]);
                succeeded = 0;
                break;
            }

            if (packets[i].payload_length != lengths[i]) {
                printf("Packet %d: actual length: %d, expected length: %d \n", i, packets[i].payload_length, lengths[i]);
                succeeded = 0;
                break;
            }

            if (strcmp(packets[i].payload, payloads[i]) != 0) {
                printf("Packet %d: actual payload: %s, expected payload: %s \n", i, packets[i].payload, payloads[i]);
                succeeded = 0;
                break;
            }

            if (packets[i].type != 0) {
                printf("Packet %d should be marked as DATA type \n", i);
                succeeded = 0;
                break;
            }
        }

        if (packets[5].type != 1) {
            printf("Packet 5 should have been marked as a LAST_DATA type \n");
            succeeded = 0;
        }

        // Uncomment this for debugging purposes
        // for (int i = 0; i < count; i++) {
        //     printf("Packet %d: payload_length=%d, payload=\"%.*s\", checksum=%d, type=%d\n",
        //            i,
        //            packets[i].payload_length,
        //            packets[i].payload_length,
        //            packets[i].payload,
        //            packets[i].checksum,
        //            packets[i].type);
        // }

        clean_up_p1_test_case:
            free(packets);

            if (!succeeded) {
                printf("Failed packetize test1, check output above \n");
            } else {
                printf("Packetize test1 passed! \n");
            }
    }

    // length % MAX_PAYLOAD_LENGTH == 0
    {
        char test3[] = "Hello, this is a test to see how packetize splits!";
        int length = strlen(test3);
        int count = 0;
        int succeeded = 1;

        packet_t *packets = packetize(test3, length, &count);

        if (count != 5) {
            succeeded = 0;
            printf("Number of packets was %d, expected to be %d\n", count, 5);
            goto clean_up_p2_test_case; // This line jumps to `clean_up_p2_test_case` so the code below doesn't execute
        }

        int checksums[] = {4039, 3957, 3739, 4551, 4170};
        int lengths[] = {10, 10, 10, 10, 10};
        char *payloads[] = {"Hello, thi", "s is a tes", "t to see h", "ow packeti", "ze splits!"};
        for (int i = 0; i < 4; i++) {
            if (packets[i].checksum != checksums[i]) {
                printf("Packet %d: actual checksum: %d, expected checksum: %d \n", i, packets[i].checksum, checksums[i]);
                succeeded = 0;
                break;
            }

            if (packets[i].payload_length != lengths[i]) {
                printf("Packet %d: actual length: %d, expected length: %d \n", i, packets[i].payload_length, lengths[i]);
                succeeded = 0;
                break;
            }

            if (strcmp(packets[i].payload, payloads[i]) != 0) {
                printf("Packet %d: actual payload: %s, expected payload: %s \n", i, packets[i].payload, payloads[i]);
                succeeded = 0;
                break;
            }

            if (packets[i].type != 0) {
                printf("Packet %d should be marked as DATA type \n", i);
                succeeded = 0;
                break;
            }
        }

        if (packets[4].type != 1) {
            printf("Packet 5 should have been marked as a LAST_DATA type \n");
            succeeded = 0;
        }

        // Uncomment this for debugging purposes
        // for (int i = 0; i < count; i++) {
        //     printf("Packet %d: payload_length=%d, payload=\"%.*s\", checksum=%d, type=%d\n",
        //            i,
        //            packets[i].payload_length,
        //            packets[i].payload_length,
        //            packets[i].payload,
        //            packets[i].checksum,
        //            packets[i].type);
        // }

        clean_up_p2_test_case:
            free(packets);

            if (!succeeded) {
                printf("Failed packetize test2, check output above \n");
            } else {
                printf("Packetize test2 passed! \n");
            }
    }
    
    return 0;
}