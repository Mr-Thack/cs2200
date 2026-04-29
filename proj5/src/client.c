#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "network.h"
#include "rtp.h"
#include "test_rtp.h"

static void printUsage()
{
    fprintf(stderr, "Usage:\n");
    fprintf(stderr, "  rtp-client host port\n");
    fprintf(stderr, "  rtp-client -t <test>\n\n");
    fprintf(stderr, "Examples:\n");
    fprintf(stderr, "  ./rtp-client localhost 4000\n");
    fprintf(stderr, "  ./rtp-client -t checksum\n");
    fprintf(stderr, "  ./rtp-client -t packetize\n\n");
    exit(EXIT_FAILURE);
}

int main(int argc, char **argv)
{

    if (argc < 2)
    {
        printUsage();
        return EXIT_FAILURE;
    }

    if (strcmp(argv[1], "-t") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Error: missing test name after -t\n\n");
            printUsage();
        }

        if (strcmp(argv[2], "checksum") == 0) {
            student_checksum_test_cases();
            return EXIT_SUCCESS;
        } else if (strcmp(argv[2], "packetize") == 0) {
            student_packetize_test_cases();
            return EXIT_SUCCESS;
        } else {
            fprintf(stderr, "Error: unknown test '%s'\n\n", argv[2]);
            printUsage();
        }
    }

    if (argc != 3) {
        printUsage();
        return EXIT_FAILURE;
    }

    char message_1[] = "Sebz gur fperra gb gur evat, gb gur cra, gb gur xvat. Jurer'f zl pebja? Gung'f zl oyvat, nyjnlf qenzn jura V evat. - XFV";

    char message_2[] = "Yvfgra lbh pehfgnprbhf purncfxngr! Fdhvqjneq'f orra yvivat va zl ubhfr qevivat zr penml! Naq lbh'er abg tbaan uver uvz onpx nyy orpnhfr bs n fghcvq qvzr?!? - FcbatrObo FdhnerCnagf";

    char message_3[] = "V'z gur jbeyq'f orfg onpxjneqf qevire. Lrf jngpu guvf evtug urer ybire - Gbj Zngre";

    char message_4[] = "Nf V njnxra sebz zl fyhzore, V eho zl rlrf, naq gurer ur vf arkg gb zr. Zl xvat. Yroeba Wnzrf. Abg npghnyyl gubhtu, whfg n yvsr-fvmr obql cvyybj zrnfhevat fvk srrg avar vapurf naq jrvtuvat 250 cbhaqf - Nabalzbhf";

    char message_5[] = "V arire gubhtug V'q yrnq gur AON va erobhaqvat, ohg V tbg n ybg bs uryc sebz zl grnz-zngrf - gurl qvq n ybg bs zvffvat - Zbfrf Znybar";

    char *rcv_buffer;
    int length, ret;
    rtp_connection_t *connection;

    if ((connection = rtp_connect(argv[1], atoi(argv[2]))) == NULL)
    {
        printUsage();
        return EXIT_FAILURE;
    }

    printf("Sending quotes to a remote host to have them "
           "decoded using ROT13 cipher!\n\n");

    rtp_send_message(connection, message_1, strlen(message_1));
    ret = rtp_recv_message(connection, &rcv_buffer, &length);
    if (rcv_buffer == NULL || ret == -1)
    {
        printf("Connection reset by peer.\n");
        return EXIT_FAILURE;
    }
    printf("%.*s\n\n", length, rcv_buffer);
    free(rcv_buffer);

    rtp_send_message(connection, message_2, strlen(message_2));
    ret = rtp_recv_message(connection, &rcv_buffer, &length);
    if (rcv_buffer == NULL || ret == -1)
    {
        printf("Connection reset by peer.\n");
        return EXIT_FAILURE;
    }
    printf("%.*s\n\n", length, rcv_buffer);
    free(rcv_buffer);

    rtp_send_message(connection, message_3, strlen(message_3));
    ret = rtp_recv_message(connection, &rcv_buffer, &length);
    if (rcv_buffer == NULL || ret == -1)
    {
        printf("Connection reset by peer.\n");
        return EXIT_FAILURE;
    }
    printf("%.*s\n\n", length, rcv_buffer);
    free(rcv_buffer);

    rtp_send_message(connection, message_4, strlen(message_4));
    ret = rtp_recv_message(connection, &rcv_buffer, &length);
    if (rcv_buffer == NULL || ret == -1)
    {
        printf("Connection reset by peer.\n");
        return EXIT_FAILURE;
    }
    printf("%.*s\n\n", length, rcv_buffer);
    free(rcv_buffer);

    rtp_send_message(connection, message_5, strlen(message_5));
    ret = rtp_recv_message(connection, &rcv_buffer, &length);
    if (rcv_buffer == NULL || ret == -1)
    {
        printf("Connection reset by peer.\n");
        return EXIT_FAILURE;
    }
    printf("%.*s\n\n", length, rcv_buffer);
    free(rcv_buffer);
    rtp_disconnect(connection);
    return EXIT_SUCCESS;
}