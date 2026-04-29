#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "network.h"
#include "queue.h"
#include "rtp.h"

/**
 * PLESE ENTER YOUR INFORMATION BELOW TO RECEIVE MANUAL GRADING CREDITS
 * Name:
 * GTID:
 * Spring 2026
 */

typedef struct message {
  char *buffer;
  int length;
} message_t;

/* ================================================================ */
/*                  H E L P E R    F U N C T I O N S                */
/* ================================================================ */

/**
 * ------- PROBLEM 1 ------
 *
 * Convert the given buffer into an array of PACKETs and returns the array.  The
 * value of (*count) should be updated so that it contains the number of packets
 * in the array. Keep in mind that if length % MAX_PAYLOAD_LENGTH != 0, you
 * might have to manually specify the payload_length.
 *
 * Hint: can we use a heap function to make space for the packets? How many
 * packets?
 *
 * @param buffer pointer to message buffer to be broken up packets
 * @param length length of the message buffer.
 * @param count number of packets in the returning array
 *
 * @returns array of packets
 */
packet_t *packetize(char *buffer, int length, int *count) {

    int num_packets = length / MAX_PAYLOAD_LENGTH;
    if (length % MAX_PAYLOAD_LENGTH != 0) {
        num_packets++;
    }

    *count = num_packets;

    packet_t *packets = (packet_t *)malloc((size_t)num_packets * sizeof(packet_t));
    if (packets == NULL) {
        return NULL;
    }

    for (int i = 0; i < num_packets; i++) {

        if (i == num_packets - 1) {
            packets[i].type = LAST_DATA;
            int remainder = length % MAX_PAYLOAD_LENGTH;
            packets[i].payload_length = (remainder == 0) ? MAX_PAYLOAD_LENGTH : remainder;
        } else {
            packets[i].type = DATA;
            packets[i].payload_length = MAX_PAYLOAD_LENGTH;
        }

        memcpy(packets[i].payload, buffer + (i * MAX_PAYLOAD_LENGTH), (size_t)packets[i].payload_length);

        packets[i].checksum = checksum(packets[i].payload, packets[i].payload_length);
    }

    return packets;
}

/**
 * ------- PROBLEM 2 ------
 *
 * Compute a checksum based on the data in the buffer.
 *
 * Checksum calcuation:
 * Suppose we are given a string in the form
 *      "a b c d e f g h"
 * Then swap each pair of characters such that the characters appear in the form
 *      "b a d c f e h g"
 *
 * If the length of the string is odd, the last character will remain in the
 * same place.
 *
 * i.e. reorder the string such that each pair of characters are swapped.
 * Following this, the checksum will be equal to the sum of the ASCII values of
 * each character multiplied by it's index in the string.
 *
 * @param buffer pointer to the char buffer that the checksum is calculated from
 * @param length length of the buffer
 *
 * @returns calcuated checksum
 */
int checksum(char *buffer, int length) {
    int sum = 0;

    for (int i = 0; i < length; i++) {
        if (i % 2 == 0) {
            if (i + 1 < length) {
                sum += buffer[i + 1] * i;
            } else {
                sum += buffer[i] * i;
            }
        } 
        else {
            sum += buffer[i - 1] * i;
        }
    }

    return sum;
}

/* ================================================================ */
/*                      R T P       T H R E A D S                   */
/* ================================================================ */

static void *rtp_recv_thread(void *void_ptr) {

  rtp_connection_t *connection = (rtp_connection_t *)void_ptr;

  do {
    message_t *message;
    int buffer_length = 0;
    char *buffer = NULL;
    packet_t packet;

    /* Put messages in buffer until the last packet is received  */
    do {
      if (net_recv_packet(connection->net_connection_handle, &packet) <= 0 ||
          packet.type == TERM) {
        /* remote side has disconnected */
        connection->alive = 0;
        pthread_cond_signal(&connection->recv_cond);
        pthread_cond_signal(&connection->send_cond);
        break;
      }

      /*  ----  FIXME: Part III-A ----
       *
       * 1. Check to make sure payload of packet is correct
       * 2. Send an ACK or a NACK, whichever is appropriate
       * 3. If this is the last packet in a sequence of packets
       *    and the payload was corrupted, make sure the loop
       *    does not terminate
       * 4. If the payload matches, add the payload to the buffer
       */

      if (packet.type == DATA || packet.type == LAST_DATA) {

          int computed_checksum = checksum(packet.payload, packet.payload_length);

          if (computed_checksum == packet.checksum) {
              packet_t ack_packet;
              ack_packet.type = ACK;
              ack_packet.payload_length = 0;
              net_send_packet(connection->net_connection_handle, &ack_packet);

              buffer = realloc(buffer, (size_t)(buffer_length + packet.payload_length));
              memcpy(buffer + buffer_length, packet.payload, (size_t)(packet.payload_length));
              buffer_length += packet.payload_length;

          } else {
              packet_t nack_packet;
              nack_packet.type = NACK;
              nack_packet.payload_length = 0;
              net_send_packet(connection->net_connection_handle, &nack_packet);

              if (packet.type == LAST_DATA) {
                  packet.type = DATA; 
              }
          }
      }
      else if (packet.type == ACK || packet.type == NACK) {

          pthread_mutex_lock(&connection->ack_mutex);

          connection->last_ack_received = packet.type;

          pthread_mutex_unlock(&connection->ack_mutex);
          pthread_cond_signal(&connection->ack_cond);
      }

    } while (packet.type != LAST_DATA);

    if (connection->alive == 1) {
      /*  ----  FIXME: Part III-B ----
       *
       * Now that an entire message has been received, we need to
       * add it to the queue to provide to the rtp client.
       *
       * 1. Add message to the received queue.
       * 2. Signal the client thread that a message has been received.
       */
        message = (message_t *)malloc(sizeof(message_t));
        message->buffer = buffer;      // The buffer you built in Part III-A
        message->length = buffer_length; 

        pthread_mutex_lock(&connection->recv_mutex);

        queue_add(&connection->recv_queue, message);

        pthread_cond_signal(&connection->recv_cond);

        pthread_mutex_unlock(&connection->recv_mutex);
    } else
      free(buffer);

  } while (connection->alive == 1);

  return NULL;
}

static void *rtp_send_thread(void *void_ptr) {

  rtp_connection_t *connection = (rtp_connection_t *)void_ptr;
  message_t *message;
  int array_length = 0;
  int i;
  packet_t *packet_array;

  do {
    /* Extract the next message from the send queue */
    pthread_mutex_lock(&connection->send_mutex);
    while (queue_size(&connection->send_queue) == 0 && connection->alive == 1) {
      pthread_cond_wait(&connection->send_cond, &connection->send_mutex);
    }

    if (connection->alive == 0) {
      pthread_mutex_unlock(&connection->send_mutex);
      break;
    }

    message = queue_extract(&connection->send_queue);

    pthread_mutex_unlock(&connection->send_mutex);

    /* Packetize the message and send it */
    packet_array = packetize(message->buffer, message->length, &array_length);

    for (i = 0; i < array_length; i++) {

      /* Start sending the packetized messages */
      if (net_send_packet(connection->net_connection_handle,
                          &packet_array[i]) <= 0) {
        /* remote side has disconnected */
        connection->alive = 0;
        break;
      }

      /*  ---- FIXME: Part III-C ----
       *
       *  1. Wait for the recv thread to notify you of when a NACK or
       *     an ACK has been received
       *  2. Check the data structure for this connection to determine
       *     if an ACK or NACK was received.  (You'll have to add the
       *     necessary fields yourself)
       *  3. If it was an ACK, continue sending the packets.
       *  4. If it was a NACK, resend the last packet
       */
      // 1. Lock the mutex before checking or waiting on the shared variable
      pthread_mutex_lock(&connection->ack_mutex);

      // Wait until the receiver thread actually updates the state with an ACK or NACK.
      // (Assume you initialize `last_ack_received` to -1 or some default before sending)
      while (connection->last_ack_received != ACK && connection->last_ack_received != NACK) {
          // This puts the thread to sleep until recv_thread calls pthread_cond_signal
          pthread_cond_wait(&connection->ack_cond, &connection->ack_mutex);
      }

      // 2 & 4. Check the data structure to determine what to do
      if (connection->last_ack_received == NACK) {
          // The packet was corrupted! We need to resend the last packet.
          // By decrementing our loop counter 'i', the for loop will just 
          // repeat the exact same packet on the next iteration.
          i--; 
      }
      // 3. If it was an ACK, we don't need an else block. The loop will 
      // naturally increment 'i' and move on to the next packet!

      // Reset our shared variable state so it's clean for the NEXT packet we send
      connection->last_ack_received = -1; 

      // Unlock the mutex so the receiver thread can use it again
      pthread_mutex_unlock(&connection->ack_mutex);
    }

    free(packet_array);
    free(message->buffer);
    free(message);
  } while (connection->alive == 1);
  return NULL;
}

/* ================================================================ */
/*                           R T P    A P I                         */
/* ================================================================ */

static rtp_connection_t *rtp_init_connection(int net_connection_handle) {
  rtp_connection_t *rtp_connection = malloc(sizeof(rtp_connection_t));

  if (rtp_connection == NULL) {
    fprintf(stderr, "Out of memory!\n");
    exit(EXIT_FAILURE);
  }

  rtp_connection->net_connection_handle = net_connection_handle;

  queue_init(&rtp_connection->recv_queue);
  queue_init(&rtp_connection->send_queue);

  pthread_mutex_init(&rtp_connection->ack_mutex, NULL);
  pthread_mutex_init(&rtp_connection->recv_mutex, NULL);
  pthread_mutex_init(&rtp_connection->send_mutex, NULL);
  pthread_cond_init(&rtp_connection->ack_cond, NULL);
  pthread_cond_init(&rtp_connection->recv_cond, NULL);
  pthread_cond_init(&rtp_connection->send_cond, NULL);

  rtp_connection->alive = 1;

  pthread_create(&rtp_connection->recv_thread, NULL, rtp_recv_thread,
                 (void *)rtp_connection);
  pthread_create(&rtp_connection->send_thread, NULL, rtp_send_thread,
                 (void *)rtp_connection);

  return rtp_connection;
}

rtp_connection_t *rtp_connect(char *host, int port) {

  int net_connection_handle;

  if ((net_connection_handle = net_connect(host, port)) < 1)
    return NULL;

  return (rtp_init_connection(net_connection_handle));
}

int rtp_disconnect(rtp_connection_t *connection) {

  message_t *message;
  packet_t term;

  term.type = TERM;
  term.payload_length = term.checksum = 0;
  net_send_packet(connection->net_connection_handle, &term);
  connection->alive = 0;

  net_disconnect(connection->net_connection_handle);
  pthread_cond_signal(&connection->send_cond);
  pthread_cond_signal(&connection->recv_cond);
  pthread_join(connection->send_thread, NULL);
  pthread_join(connection->recv_thread, NULL);
  net_release(connection->net_connection_handle);

  /* emtpy recv queue and free allocated memory */
  while ((message = queue_extract(&connection->recv_queue)) != NULL) {
    free(message->buffer);
    free(message);
  }
  queue_release(&connection->recv_queue);

  /* emtpy send queue and free allocated memory */
  while ((message = queue_extract(&connection->send_queue)) != NULL) {
    free(message);
  }
  queue_release(&connection->send_queue);

  free(connection);

  return 1;
}

int rtp_recv_message(rtp_connection_t *connection, char **buffer, int *length) {

  message_t *message;

  if (connection->alive == 0)
    return -1;
  /* lock */
  pthread_mutex_lock(&connection->recv_mutex);
  while (queue_size(&connection->recv_queue) == 0 && connection->alive == 1) {
    pthread_cond_wait(&connection->recv_cond, &connection->recv_mutex);
  }

  if (connection->alive == 0) {
    pthread_mutex_unlock(&connection->recv_mutex);
    return -1;
  }

  /* extract */
  message = queue_extract(&connection->recv_queue);
  *buffer = message->buffer;
  *length = message->length;
  free(message);

  /* unlock */
  pthread_mutex_unlock(&connection->recv_mutex);

  return *length;
}

int rtp_send_message(rtp_connection_t *connection, char *buffer, int length) {

  message_t *message;

  if (connection->alive == 0)
    return -1;

  message = malloc(sizeof(message_t));
  if (message == NULL) {
    return -1;
  }
  message->buffer = malloc((size_t)length);
  message->length = length;

  if (message->buffer == NULL) {
    free(message);
    return -1;
  }

  memcpy(message->buffer, buffer, (size_t)length);

  /* lock */
  pthread_mutex_lock(&connection->send_mutex);

  /* add */
  queue_add(&(connection->send_queue), message);

  /* unlock */
  pthread_mutex_unlock(&connection->send_mutex);
  pthread_cond_signal(&connection->send_cond);
  return 1;
}
