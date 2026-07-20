#include <stdint.h>

static volatile uint32_t runtime_seed = 0x9e3779b9u;

__attribute__((visibility("default")))
uint32_t fixture_control_flow(uint32_t value) {
    uint32_t state = 0;
    uint32_t result = value;
    for (;;) {
        switch (state) {
        case 0:
            result ^= runtime_seed;
            state = ((result | 1u) * (result | 1u)) % 2u == 1u ? 3u : 5u;
            break;
        case 3:
            result = (result << 7) | (result >> 25);
            state = 8;
            break;
        case 5:
            result ^= 0xdeadbeefu;
            state = 8;
            break;
        case 8:
            return result + 0x10203040u;
        default:
            return 0;
        }
    }
}
