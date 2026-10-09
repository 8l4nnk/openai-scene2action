// Normalized 2D swept disk versus expanded AABBs. Not robot 3D geometry.
#include <algorithm>
#include <cmath>
#include <cstddef>

#if defined(_WIN32)
#define S2A_EXPORT extern "C" __declspec(dllexport)
#else
#define S2A_EXPORT extern "C" __attribute__((visibility("default")))
#endif

S2A_EXPORT int s2a_geometry_abi() noexcept { return 1; }

// 1 = clear, 0 = blocked, -1 = invalid input. No allocations, I/O or state.
S2A_EXPORT int s2a_path_clear(const double* points, std::size_t count,
                             const double* boxes, std::size_t box_count,
                             double radius) noexcept {
    if (!points || count < 2 || count > 1024 || box_count > 4096 ||
        (box_count && !boxes) || !std::isfinite(radius) || radius < 0 || radius > .5)
        return -1;
    for (std::size_t i = 0; i < count * 2; ++i)
        if (!std::isfinite(points[i]) || points[i] < radius || points[i] > 1 - radius)
            return 0;
    for (std::size_t i = 0; i < box_count; ++i) {
        const auto* box = boxes + i * 4;
        for (int k = 0; k < 4; ++k)
            if (!std::isfinite(box[k]) || box[k] < 0 || box[k] > 1) return -1;
        if (box[0] > box[2] || box[1] > box[3]) return -1;
    }
    for (std::size_t i = 1; i < count; ++i) {
        const auto* start = points + (i - 1) * 2;
        const auto* end = points + i * 2;
        for (std::size_t j = 0; j < box_count; ++j) {
            const auto* box = boxes + j * 4;
            double low = 0, high = 1;
            for (int axis = 0; axis < 2; ++axis) {
                const double delta = end[axis] - start[axis];
                const double lower = box[axis] - radius;
                const double upper = box[axis + 2] + radius;
                if (std::abs(delta) < 1e-12) {
                    if (std::max(start[axis], end[axis]) < lower ||
                        std::min(start[axis], end[axis]) > upper) {
                        low = 1; high = 0; break;
                    }
                } else {
                    const double t0 = (lower - start[axis]) / delta;
                    const double t1 = (upper - start[axis]) / delta;
                    low = std::max(low, std::min(t0, t1));
                    high = std::min(high, std::max(t0, t1));
                }
            }
            if (low <= high) return 0;
        }
    }
    return 1;
}
