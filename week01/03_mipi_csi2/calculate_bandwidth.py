"""实验 1：Camera 带宽计算器

背景：Day 2 已经证明 RAW10 在 MIPI 上以 4 像素 → 5 字节 packed 传输。
本脚本把"分辨率 × 位深 × 帧率 × lane 数"换算成工程上真正关心的指标：

    - 每帧多少像素 / bit / byte
    - 每秒多少 MB / MiB（两种单位都给出）
    - 有效载荷 Gbps 与含协议开销的链路 Gbps
    - 每个 lane 要承担的速率
    - 给定 lane 速率下最少需要几个 lane

单位约定（本实验重点）：
    MB  = 10^6 bytes（十进制，网络/存储行业常用）
    MiB = 2^20 bytes（二进制，操作系统常用）
    带宽估算最常见的错误就是把两者混用（如把 2.472 MiB 写成 2.47 MB）。

用法：
    python calculate_bandwidth.py
    python calculate_bandwidth.py --width 3840 --height 2160 --bit-depth 12 --fps 30 --lanes 4
    python calculate_bandwidth.py --table
"""

import argparse
import math

# MIPI RAW packed 格式每像素字节数（见 02_bayer/raw10_packing.py 实验）
PACKED_BYTES_PER_PIXEL = {
    8: 1.0,    # RAW8  : 每像素整 1 字节
    10: 1.25,   # RAW10 : 4 像素 → 5 字节
    12: 1.5,    # RAW12 : 2 像素 → 3 字节
    14: 1.75,   # RAW14 : 4 像素 → 7 字节
    16: 2.0,    # RAW16 : 每像素 2 字节
}

# D-PHY 各版本单 lane 最大速率（Gbps/lane），用作"需要几个 lane"的参考
D_PHY_GENERATIONS = {
    "D-PHY v1.1": 1.5,
    "D-PHY v1.2": 2.5,
    "D-PHY v2.0": 4.5,
}

# 协议开销估算：FS/FE/LS/LE 短包 + 长包 Header(4B) + CRC(2B) + 帧间消隐，
# 实际链路利用率一般在 75~85%，这里取 25% 开销。
OVERHEAD = 0.25


def calculate(width, height, bit_depth, fps, lanes=1):
    """返回带宽指标 dict。所有字节数都是 packed 有效载荷口径。"""
    pixels = width * height
    bits_per_frame = pixels * bit_depth                # 有效载荷 bit 数
    packed_bytes_per_frame = pixels * PACKED_BYTES_PER_PIXEL[bit_depth]
    bytes_per_second = packed_bytes_per_frame * fps
    payload_gbps = bytes_per_second * 8 / 1e9
    link_gbps = payload_gbps * (1 + OVERHEAD)          # 含协议开销的链路速率
    return {
        "pixels": pixels,
        "bits_per_frame": bits_per_frame,
        "bytes_per_frame": packed_bytes_per_frame,
        "bytes_per_second": bytes_per_second,
        "payload_gbps": payload_gbps,
        "link_gbps": link_gbps,
        "payload_gbps_per_lane": payload_gbps / lanes,
        "link_gbps_per_lane": link_gbps / lanes,
    }


def lanes_needed(link_gbps, lane_rate_gbps):
    """链路速率 ÷ 单 lane 速率，向上取整 = 最少 lane 数。"""
    return max(1, math.ceil(link_gbps / lane_rate_gbps))


def print_result(width, height, bit_depth, fps, lanes):
    r = calculate(width, height, bit_depth, fps, lanes)
    bpf = r["bytes_per_frame"]
    print(f"{width}x{height}  RAW{bit_depth}  {fps} fps  {lanes} lane(s)")
    print(f"  像素/帧      : {r['pixels']:,}")
    print(f"  有效 bit/帧  : {r['bits_per_frame']:,}")
    print(f"  有效 byte/帧 : {bpf:,}")
    print(f"     = {bpf/1e6:.3f} MB/帧  (十进制)   ← 换算带宽时统一用这个")
    print(f"     = {bpf/2**20:.3f} MiB/帧 (二进制)")
    print(f"  数据率       : {r['bytes_per_second']/1e6:,.2f} MB/s")
    print(f"     = {r['bytes_per_second']/2**20:,.2f} MiB/s")
    print(f"  有效载荷     : {r['payload_gbps']:.3f} Gbps")
    print(f"  含开销({OVERHEAD:.0%})链路: {r['link_gbps']:.3f} Gbps")
    print(f"  每 lane 承担 : {r['payload_gbps_per_lane']:.3f} Gbps (载荷) / "
          f"{r['link_gbps_per_lane']:.3f} Gbps (含开销)")
    print("  最少 lane 数（按各代 D-PHY 速率）:")
    for gen, rate in D_PHY_GENERATIONS.items():
        n = lanes_needed(r["link_gbps"], rate)
        print(f"    {gen:12s} {rate:.1f} Gbps/lane -> 至少 {n} lane")


# 实验 2 的四组典型配置
PRESETS = [
    ("1080P", 1920, 1080, 10, 30),
    ("1080P", 1920, 1080, 10, 60),
    ("4K", 3840, 2160, 10, 30),
    ("4K", 3840, 2160, 12, 30),
]


def print_table():
    print("| 分辨率 | RAW | FPS | 像素/帧 | 载荷 MB/帧 | 数据率 MB/s | 数据率 Gbps | 含开销 Gbps | 最少 lane @1.5G | 最少 lane @2.5G |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, w, h, bd, fps in PRESETS:
        r = calculate(w, h, bd, fps, lanes=1)  # lane 数与数据率无关，先按 1 算总量
        print(f"| {name} | RAW{bd} | {fps} | {r['pixels']:,} | "
              f"{r['bytes_per_frame']/1e6:.3f} | {r['bytes_per_second']/1e6:,.1f} | "
              f"{r['payload_gbps']:.3f} | {r['link_gbps']:.3f} | "
              f"{lanes_needed(r['link_gbps'], 1.5)} | {lanes_needed(r['link_gbps'], 2.5)} |")


def main():
    p = argparse.ArgumentParser(description="Camera 带宽计算器")
    p.add_argument("--width", type=int, default=1920)
    p.add_argument("--height", type=int, default=1080)
    p.add_argument("--bit-depth", type=int, default=10, choices=[8, 10, 12, 14, 16])
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--lanes", type=int, default=2)
    p.add_argument("--table", action="store_true", help="打印实验 2 的四组配置对比表")
    args = p.parse_args()

    if args.table:
        print_table()
    else:
        print_result(args.width, args.height, args.bit_depth, args.fps, args.lanes)


if __name__ == "__main__":
    main()
