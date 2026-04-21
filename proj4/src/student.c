/*
 * student.c
 * Multithreaded OS Simulation for CS 2200
 * Spring 2026
 *
 * This file contains the CPU scheduler for the simulation.
 */

#include <assert.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "student.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

/** Function prototypes **/
extern void idle(unsigned int cpu_id);
extern void on_preempt(unsigned int cpu_id);
extern void yield(unsigned int cpu_id);
extern void terminate(unsigned int cpu_id);
extern void wake_up(pcb_t *process);

static unsigned int cpu_count;

/*
 * current[] is an array of pointers to the currently running processes.
 * There is one array element corresponding to each CPU in the simulation.
 *
 * current[] should be updated by schedule() each time a process is scheduled
 * on a CPU.  Since the current[] array is accessed by multiple threads, you
 * will need to use a mutex to protect it.  current_mutex has been provided
 * for your use.
 *
 * rq is a pointer to a struct you should use for your ready queue
 * implementation. The head of the queue corresponds to the process
 * that is about to be scheduled onto the CPU, and the tail is for
 * convenience in the enqueue function. See student.h for the
 * relevant function and struct declarations.
 *
 * Similar to current[], rq is accessed by multiple threads,
 * so you will need to use a mutex to protect it. ready_mutex has been
 * provided for that purpose.
 *
 * The condition variable queue_not_empty has been provided for you
 * to use in conditional waits and signals.
 *
 * Please look up documentation on how to properly use pthread_mutex_t
 * and pthread_cond_t.
 *
 * A scheduler_algorithm variable and sched_algorithm_t enum have also been
 * supplied to you to keep track of your scheduler's current scheduling
 * algorithm. You should update this variable according to the program's
 * command-line arguments. Read student.h for the definitions of this type.
 */
static pcb_t **current;
static queue_t *rq;

static pthread_mutex_t current_mutex;
static pthread_mutex_t queue_mutex;
static pthread_cond_t queue_not_empty;

static sched_algorithm_t scheduler_algorithm;
static unsigned int cpu_count;
static int timeslice = -1;

/** ------------------------Problem 0 & 3-----------------------------------
 * Checkout PDF Section 2 and 5 for this problem
 *
 * enqueue() is a helper function to add a process to the ready queue.
 *
 * NOTE: For Priority, FCFS, and SRTF scheduling, you will need to have
 * additional logic in this function and/or the dequeue function to pick the
 * process with the smallest priority.
 *
 *
 * @param queue pointer to the ready queue
 * @param process process that we need to put in the ready queue
 */
void enqueue(queue_t *queue, pcb_t *process) {
    process->next = NULL; 
    if (is_empty(queue)) {
        queue->head = process;
        queue->tail = process;
    } else {
        // just add to tail
        queue->tail->next = process;
        queue->tail = process;
    }
}

/**
 * dequeue() is a helper function to remove a process to the ready queue.
 *
 * NOTE: For Priority, FCFS, and SRTF scheduling, you will need to have
 * additional logic in this function and/or the enqueue function to pick the
 * process with the smallest priority.
 *
 *
 * @param queue pointer to the ready queue
 */
pcb_t *dequeue(queue_t *queue) {
    if (is_empty(queue)) return NULL;

    if (scheduler_algorithm == RR) {
        pcb_t *process = queue->head;
        queue->head = queue->head->next;

        if (queue->head == NULL) {
            queue->tail = NULL;
        }
        process->next = NULL;
        return process;
    }

    /* For FCFS, PRIORITY, and SRTF, we must search for the "best" process */
    pcb_t *best = queue->head;
    pcb_t *best_prev = NULL;

    pcb_t *curr = queue->head;
    pcb_t *prev = NULL;

    while (curr != NULL) {
        bool is_better = false;

        if (scheduler_algorithm == FCFS) {
            if (curr->arrival_time < best->arrival_time) is_better = true;
        } else if (scheduler_algorithm == PRIORITY) {
            if (curr->priority < best->priority) is_better = true;
        } else if (scheduler_algorithm == SRTF) {
            if (curr->total_time_remaining < best->total_time_remaining) is_better = true;
        }

        if (is_better) {
            best = curr;
            best_prev = prev;
        }
        prev = curr;
        curr = curr->next;
    }

    /* Safely remove the 'best' process from the linked list */
    if (best_prev == NULL) {
        queue->head = queue->head->next;
        if (queue->head == NULL) {
            queue->tail = NULL;
        }
    } else {
        best_prev->next = best->next;
        if (best->next == NULL) {
            queue->tail = best_prev; // Update tail if we removed the last element
        }
    }

    best->next = NULL;
    return best;
}

/** ------------------------Problem 0-----------------------------------
 * Checkout PDF Section 2 for this problem
 *
 * is_empty() is a helper function that returns whether the ready queue
 * has any processes in it.
 *
 * @param queue pointer to the ready queue
 *
 * @return a boolean value that indicates whether the queue is empty or not
 */
bool is_empty(queue_t *queue) {
    return queue->head == NULL;
}

/** ------------------------Problem 1B-----------------------------------
 * Checkout PDF Section 3 for this problem
 *
 * schedule() is your CPU scheduler.
 *
 * Remember to specify the timeslice if the scheduling algorithm is Round-Robin
 *
 * @param cpu_id the target cpu we decide to put our process in
 */
static void schedule(unsigned int cpu_id) { 
    pcb_t *process;

    /* 1. Safely extract a process from the ready queue */
    pthread_mutex_lock(&queue_mutex);
    process = dequeue(rq);
    pthread_mutex_unlock(&queue_mutex);

    /* 2. Update the process state if we found one */
    if (process != NULL) {
        process->state = PROCESS_RUNNING;
    }

    /* 3. Safely update the global current[] array */
    pthread_mutex_lock(&current_mutex);
    current[cpu_id] = process;
    pthread_mutex_unlock(&current_mutex);

    /* 4. Tell the simulator to run it (-1 for infinite timeslice in FCFS) */
    context_switch(cpu_id, process, timeslice);
}

/**  ------------------------Problem 1A-----------------------------------
 * Checkout PDF Section 3 for this problem
 *
 * idle() is your idle process.  It is called by the simulator when the idle
 * process is scheduled. This function should block until a process is added
 * to your ready queue.
 *
 * @param cpu_id the cpu that is waiting for process to come in
 */
extern void idle(unsigned int cpu_id) {
    /* Block until the ready queue is no longer empty */
    pthread_mutex_lock(&queue_mutex);
    while (is_empty(rq)) {
        pthread_cond_wait(&queue_not_empty, &queue_mutex);
    }
    pthread_mutex_unlock(&queue_mutex);

    /* Now that something is in the queue, schedule it! */
    schedule(cpu_id);
}

/** ------------------------Problem 2 & 3-----------------------------------
 * Checkout Section 4 and 5 for this problem
 *
 * on_preempt() is the handler used in Round-robin, Preemptive Priority, and
 * SRTF scheduling.
 *
 * This function should place the currently running process back in the
 * ready queue, and call schedule() to select a new runnable process.
 *
 * @param cpu_id the cpu in which we want to preempt process
 */
extern void on_preempt(unsigned int cpu_id) {
    /* 1. Safely grab the current process and update state */
    pthread_mutex_lock(&current_mutex);
    pcb_t *process = current[cpu_id];
    if (process != NULL) {
        process->state = PROCESS_READY;
    } 
    pthread_mutex_unlock(&current_mutex);

    /* 2. Put it back in the ready queue */
    if (process != NULL) {
        pthread_mutex_lock(&queue_mutex);
        enqueue(rq, process);
        pthread_mutex_unlock(&queue_mutex);
    }

    /* 3. Schedule the next process */
    schedule(cpu_id);
}

/**  ------------------------Problem 1A-----------------------------------
 * Checkout PDF Section 3 for this problem
 *
 * yield() is the handler called by the simulator when a process yields the
 * CPU to perform an I/O request.
 *
 * @param cpu_id the cpu that is yielded by the process
 */
extern void yield(unsigned int cpu_id) {
    pthread_mutex_lock(&current_mutex);
    if (current[cpu_id] != NULL) {
        current[cpu_id]->state = PROCESS_WAITING;
    }
    pthread_mutex_unlock(&current_mutex);

    schedule(cpu_id);
}

/**  ------------------------Problem 1A-----------------------------------
 * Checkout PDF Section 3
 *
 * terminate() is the handler called by the simulator when a process completes.
 *
 * @param cpu_id the cpu we want to terminate
 */
extern void terminate(unsigned int cpu_id) {
    pthread_mutex_lock(&current_mutex);
    if (current[cpu_id] != NULL) {
        current[cpu_id]->state = PROCESS_TERMINATED;
    }
    pthread_mutex_unlock(&current_mutex);

    schedule(cpu_id);
}

/**  ------------------------Problem 1A & 3---------------------------------
 * Checkout PDF Section 3 and 5 for this problem
 *
 * wake_up() is the handler called by the simulator when a process's I/O
 * request completes.
 * This method will also need to handle priority and SRTF preemption.
 * Look in section 5 of the PDF for more info.
 *
 * We've provided an API for marking a CPU for preemption via
 * `mark_for_preemption(unsigned int cpu_id)`
 *
 * @param process the process that finishes I/O and is ready to run on CPU
 */
extern void wake_up(pcb_t *process) { 
    process->state = PROCESS_READY;

    /* 1. Safely add to the ready queue and wake up sleeping CPUs */
    pthread_mutex_lock(&queue_mutex);
    enqueue(rq, process);
    pthread_cond_signal(&queue_not_empty); 
    pthread_mutex_unlock(&queue_mutex);

    /* 2. Preemption Logic for Priority and SRTF */
    if (scheduler_algorithm == PRIORITY || scheduler_algorithm == SRTF) {
        pthread_mutex_lock(&current_mutex);

        bool has_idle_cpu = false;
        for (unsigned int i = 0; i < cpu_count; i++) {
            if (current[i] == NULL) {
                has_idle_cpu = true;
                break;
            }
        }

        if (!has_idle_cpu) {
            unsigned int worst_cpu = 0;
            pcb_t *worst_process = current[0];

            /* Scan all CPUs to find the "worst" running process */
            for (unsigned int i = 1; i < cpu_count; i++) {
                /* Priority: higher int = lower priority */
                if (scheduler_algorithm == PRIORITY && current[i]->priority > worst_process->priority) {
                    worst_process = current[i];
                    worst_cpu = i;
                } 
                /* SRTF: higher int = more time remaining */
                else if (scheduler_algorithm == SRTF && current[i]->total_time_remaining > worst_process->total_time_remaining) {
                    worst_process = current[i];
                    worst_cpu = i;
                }
            }

            /* If all CPUs are busy, check if our newly awakened process is better than the worst one */
            bool should_preempt = false;

            if (scheduler_algorithm == PRIORITY && process->priority < worst_process->priority) {
                should_preempt = true;
            } else if (scheduler_algorithm == SRTF && process->total_time_remaining < worst_process->total_time_remaining) {
                should_preempt = true;
            }

            if (should_preempt) {
                mark_for_preemption(worst_cpu);
            }
        }

        pthread_mutex_unlock(&current_mutex);
    }
}

/**
 * main() simply parses command line arguments, then calls start_simulator().
 *
 */
int main(int argc, char *argv[]) {
  /* FIX ME */
  scheduler_algorithm = FCFS;

  if (argc == 3 && !strcmp(argv[2], "-p")) {
    scheduler_algorithm = PRIORITY;
  } else if (argc == 4 && !strcmp(argv[2], "-r")) {
    scheduler_algorithm = RR;
    timeslice = atoi(argv[3]);
  } else if (argc == 3 && !strcmp(argv[2], "-s")) {
    scheduler_algorithm = SRTF;
  } else if (argc != 2) {
    fprintf(stderr, "CS 2200 Project 4 -- Multithreaded OS Simulator\n"
                    "Usage: ./os-sim <# CPUs> [ -r <time slice> | -p | -s ]\n"
                    "    Default : FCFS Scheduler\n"
                    "         -p : Priority Aging Scheduler\n"
                    "         -r : Round Robin Scheduler\n"
                    "         -s : Shortest Remaining Time First\n");
    return -1;
  }

  /* Parse the command line arguments */
  cpu_count = strtoul(argv[1], NULL, 0);

  /* Allocate the current[] array and its mutex */
  current = calloc(cpu_count, sizeof(pcb_t *));
  assert(current != NULL);
  pthread_mutex_init(&current_mutex, NULL);
  pthread_mutex_init(&queue_mutex, NULL);
  pthread_cond_init(&queue_not_empty, NULL);
  rq = (queue_t *)malloc(sizeof(queue_t));
  assert(rq != NULL);

  rq->head = NULL;
  rq->tail = NULL;

  /* Start the simulator in the library */
  start_simulator(cpu_count);

  return 0;
}

#pragma GCC diagnostic pop
