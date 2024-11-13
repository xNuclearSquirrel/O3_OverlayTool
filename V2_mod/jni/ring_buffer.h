// ring_buffer.h
#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <pthread.h>
#include <stdint.h>

// Define the maximum size of the OSD frame data
#define MAX_GRID_SIZE 2000   // 1060 should already be enough

// Define the size of the ring buffer
#define RING_BUFFER_SIZE 10  // Adjust based on performance requirements

// Structure for OSD frame data
typedef struct {
    uint8_t osd_frame_data[MAX_GRID_SIZE];
    size_t data_size;
    uint32_t grid_width;
    uint32_t grid_height;
    uint64_t delta_time; // Delta time in nanoseconds
} RingBufferEntry;

// Structure for the ring buffer
typedef struct {
    RingBufferEntry entries[RING_BUFFER_SIZE];
    int head;
    int tail;
    pthread_mutex_t mutex;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
} ring_buffer_t;

// Declare the ring buffer and recording flag as extern variables
extern ring_buffer_t ring_buffer;
extern volatile int recording_active;
extern uint64_t recording_start_time; // For delta time calculation

#endif // RING_BUFFER_H