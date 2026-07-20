#include <stddef.h>
#include <stdint.h>

__attribute__((visibility("default")))
uint32_t fixture_checksum(const uint8_t *data, size_t length) {
    uint32_t state = 2166136261u;
    for (size_t index = 0; index < length; ++index) {
        state = (state ^ data[index]) * 16777619u;
    }
    return state;
}
