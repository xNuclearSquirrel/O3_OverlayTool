// MxDisplayPortDisplayPort_DrawScreen.c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <pthread.h>
#include <string.h>     // For memcpy

#include "ring_buffer.h"  // Include the header file

// Declare the original function pointers
typedef void (*orig_MxDisplayPortDisplayPort_DrawScreen_t)(int, int);
typedef void* (*orig_MxContainerDynamicArray_At_t)(int, int, uint32_t, uint32_t);

static orig_MxDisplayPortDisplayPort_DrawScreen_t orig_func = NULL;
static orig_MxContainerDynamicArray_At_t orig_MxContainerDynamicArray_At = NULL;

void MxDisplayPortDisplayPort_DrawScreen(int param_1, int param_2) {
    // Load the original function if not already loaded
    if (orig_func == NULL) {
        orig_func = (orig_MxDisplayPortDisplayPort_DrawScreen_t)dlsym(RTLD_NEXT, "MxDisplayPortDisplayPort_DrawScreen");
        if (!orig_func) {
            return;
        }
    }

    if (orig_MxContainerDynamicArray_At == NULL) {
        orig_MxContainerDynamicArray_At = (orig_MxContainerDynamicArray_At_t)dlsym(RTLD_NEXT, "MxContainerDynamicArray_At");
        if (!orig_MxContainerDynamicArray_At) {
            return;
        }
    }

    // Call the original function
    orig_func(param_1, param_2);

    if (recording_active) {
        // Collect OSD data

        // Retrieve rows and columns directly from param_1
        int rows = *(int *)(param_1 + 0x70);
        int columns = *(int *)(param_1 + 0x74);

        // Validate grid size
        int grid_size = rows * columns;
        if (grid_size <= 0 || grid_size > MAX_GRID_SIZE) {
            return;
        }

		// Prepare the ring buffer entry
		RingBufferEntry entry;
		entry.data_size = grid_size;
		entry.grid_width = columns;
		entry.grid_height = rows;

		// Get current time and calculate delta time
		struct timespec ts;
		clock_gettime(CLOCK_MONOTONIC, &ts);
		uint64_t current_time = ts.tv_sec * 1000000000ULL + ts.tv_nsec;
		entry.delta_time = current_time - recording_start_time;

		// Fill the ring buffer entry directly
		for (int row = 0; row < rows; row++) {
			for (int col = 0; col < columns; col++) {
				int index = row * columns + col;

				void *data_ptr = orig_MxContainerDynamicArray_At(param_2, index, 0, 0);
				if (data_ptr) {
					// Access the OSD byte at offset +16
					uint8_t value = *((uint8_t*)data_ptr + 16); // that's where the OSD byte is.
					entry.osd_frame_data[index] = value;
				} else {
					entry.osd_frame_data[index] = 0x00; // empty square
				}
			}
		}

		// Lock the ring buffer
		pthread_mutex_lock(&ring_buffer.mutex);

		// Check if the buffer is full
		if (((ring_buffer.head + 1) % RING_BUFFER_SIZE) == ring_buffer.tail) {
			// Buffer is full; advance tail to overwrite oldest data
			ring_buffer.tail = (ring_buffer.tail + 1) % RING_BUFFER_SIZE;
		}

		// Add data to the ring buffer
		ring_buffer.entries[ring_buffer.head] = entry;
		ring_buffer.head = (ring_buffer.head + 1) % RING_BUFFER_SIZE;

		// Signal that the ring buffer is not empty
		pthread_cond_signal(&ring_buffer.not_empty);

		// Unlock the ring buffer
		pthread_mutex_unlock(&ring_buffer.mutex);
	}
}