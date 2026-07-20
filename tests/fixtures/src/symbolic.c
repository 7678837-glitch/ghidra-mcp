#include <stdint.h>

static int32_t mix(int32_t value) {
    return (value ^ 0x13579bdf) + 17;
}

__attribute__((visibility("default")))
int32_t fixture_symbolic(int32_t left, int32_t right) {
    return mix(left) + right;
}
