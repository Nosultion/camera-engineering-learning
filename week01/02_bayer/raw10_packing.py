"""实验 3：RAW10 Packing / Unpacking（MIPI CSI-2 格式）

为什么需要 packing：
RAW10 每像素 10 bit。如果简单用 uint16 存，每像素浪费 6 bit，
MIPI CSI-2 上的真实做法是把 4 个像素压进 5 个字节：

    4 pixels × 10 bit = 40 bit = 5 bytes

每个像素变成 1.25 bytes，比 uint16 (2 bytes) 节省 37.5%。

本文件实现 MIPI CSI-2 RAW10 的 packed 布局：

    byte0 = P0[9:2]   （P0 高 8 位）
    byte1 = P1[9:2]
    byte2 = P2[9:2]
    byte3 = P3[9:2]
    byte4 = P3[1:0] << 6 | P2[1:0] << 4 | P1[1:0] << 2 | P0[1:0]
            （4 个像素的低 2 位，从高位到低位按 P3 P2 P1 P0 排列）

注意：这只是 MIPI 的字节布局之一（对应 MEDIA_BUS_FMT_SRGGB10_1X10 中的
1X10，即 1 像素对应 1 个 10-bit word）。Packing 的"总账"永远一样：
4 × 10 bit = 40 bit = 5 bytes。

用法：
    python raw10_packing.py
读取 output/bayer_raw10.raw，输出：
    output/bayer_raw10_packed.raw   (packed 字节流)
并做 round-trip 验证。
"""

from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"


# ---------------------------------------------------------------- scalar 版
# 可读的逐像素实现，用于讲清楚字节布局，也作为 vectorized 版的对照。

def pack4_mipi(p0: int, p1: int, p2: int, p3: int) -> bytes:
    """把 4 个 10-bit 像素 (0~1023) 打包成 5 bytes。"""
    for p in (p0, p1, p2, p3):
        assert 0 <= p < 1024, f"像素值超出 10-bit 范围: {p}"
    b0 = (p0 >> 2) & 0xFF
    b1 = (p1 >> 2) & 0xFF
    b2 = (p2 >> 2) & 0xFF
    b3 = (p3 >> 2) & 0xFF
    b4 = ((p3 & 0x3) << 6) | ((p2 & 0x3) << 4) | ((p1 & 0x3) << 2) | (p0 & 0x3)
    return bytes([b0, b1, b2, b3, b4])


def unpack4_mipi(data: bytes) -> tuple:
    """把 5 bytes 解包回 4 个 10-bit 像素。"""
    assert len(data) == 5, "RAW10 packed 单元必须是 5 bytes"
    b0, b1, b2, b3, b4 = data
    p0 = (b0 << 2) | (b4 & 0x3)
    p1 = (b1 << 2) | ((b4 >> 2) & 0x3)
    p2 = (b2 << 2) | ((b4 >> 4) & 0x3)
    p3 = (b3 << 2) | ((b4 >> 6) & 0x3)
    return p0, p1, p2, p3


# ------------------------------------------------------------ vectorized 版
# 用 numpy 对整个图像（甚至整个帧）做打包/解包。

def pack_raw10_mipi(raw10: np.ndarray) -> np.ndarray:
    """uint16 数组 (H, W) -> packed 字节数组 (H, W//4*5)。

    每行按 4 像素一组；行宽不足 4 的倍数时先补 0
    （真实 Sensor 的 line width 也会按 MIPI 对齐要求做填充）。
    """
    h, w = raw10.shape
    w_pad = (w + 3) // 4 * 4
    padded = np.zeros((h, w_pad), dtype=np.uint16)
    padded[:, :w] = raw10

    groups = padded.reshape(h, w_pad // 4, 4)  # 每 4 像素一组

    hi = (groups >> 2).astype(np.uint8)        # 每像素高 8 位 -> 4 个字节
    lo = groups & 0x3                          # 每像素低 2 位
    lsb_byte = ((lo[:, :, 3] << 6) | (lo[:, :, 2] << 4)
                | (lo[:, :, 1] << 2) | lo[:, :, 0])  # 第 5 个字节

    packed = np.dstack([hi, lsb_byte[..., None]]).reshape(h, w_pad // 4 * 5)
    return packed.astype(np.uint8)


def unpack_raw10_mipi(packed: np.ndarray, width: int) -> np.ndarray:
    """packed 字节数组 (H, W//4*5) -> uint16 数组 (H, width)。

    解包不需要知道对齐宽度，只需要知道图像真实宽度 width。
    """
    h = packed.shape[0]
    groups = packed.reshape(h, packed.shape[1] // 5, 5)

    hi = groups[:, :, :4].astype(np.uint16) << 2   # 高 8 位左移 2 位
    b4 = groups[:, :, 4]                           # 低 2 位所在的第 5 字节
    lo = np.dstack([b4 & 0x3, (b4 >> 2) & 0x3, (b4 >> 4) & 0x3, (b4 >> 6) & 0x3])

    pixels = (hi + lo).reshape(h, -1)
    return pixels[:, :width]


# ------------------------------------------------------------------- 测试

def test_scalar_roundtrip() -> None:
    print("== 测试 1: 手算示例 ==")
    demo = [1023, 0, 682, 341]   # 0x3FF, 0x000, 0x2AA, 0x155
    packed = pack4_mipi(*demo)
    print(f"  pixels: {demo}")
    print(f"  packed: {packed.hex(' ').upper()}  (期望 FF 00 AA 55 63)")
    assert packed == bytes([0xFF, 0x00, 0xAA, 0x55, 0x63])
    assert unpack4_mipi(packed) == tuple(demo)
    print("  unpack: OK")

    print("\n== 测试 2: 边界值 ==")
    for case in [(0, 0, 0, 0), (1023, 1023, 1023, 1023), (1, 2, 3, 4)]:
        assert unpack4_mipi(pack4_mipi(*case)) == case
    print("  0x000/0x3FF/1,2,3,4 round-trip: OK")

    print("\n== 测试 3: 0~1023 全值域 round-trip ==")
    rng = np.random.default_rng(42)
    vals = rng.permutation(1024)              # 打乱顺序覆盖所有值
    for i in range(0, 1024, 4):
        group = tuple(int(v) for v in vals[i:i+4])
        assert unpack4_mipi(pack4_mipi(*group)) == group
    print("  全部 1024 个值 round-trip: OK")


def test_image_roundtrip(raw10: np.ndarray) -> np.ndarray:
    h, w = raw10.shape
    print("\n== 测试 4: 整幅图 pack/unpack ==")

    packed = pack_raw10_mipi(raw10)
    print(f"  uint16 未打包 : {w*h*2:>8} bytes  (2.00 bytes/px)")
    print(f"  RAW10 packed  : {packed.size:>8} bytes  "
          f"({packed.size/(w*h):.2f} bytes/px)")

    # vectorized 版与 scalar 版交叉验证（取左上角前 100 组）
    for i in range(0, 100 * 4, 4):
        row = packed[0]
        sc = pack4_mipi(*[int(v) for v in raw10[0, i:i+4]])
        assert (row[i // 4 * 5:(i // 4 + 1) * 5] == np.frombuffer(sc, np.uint8)).all()
    print("  vectorized 版与 scalar 版逐字节一致: OK")

    restored = unpack_raw10_mipi(packed, w)
    assert np.array_equal(restored, raw10), "整幅图 round-trip 不一致！"
    print("  整幅图 round-trip: OK, 数据完全一致")
    return packed


def main() -> None:
    test_scalar_roundtrip()

    # 真实系统中，分辨率由驱动 / V4L2 格式配置告知接收端；
    # 这里用 16-bit PNG 作为带尺寸信息的容器来读取。
    png_path = OUTPUT_DIR / "raw10_unpacked.png"
    if not png_path.exists():
        raise SystemExit("找不到 output/raw10_unpacked.png，请先运行 generate_raw10.py")
    raw10 = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED).astype(np.uint16)

    packed = test_image_roundtrip(raw10)

    packed_path = OUTPUT_DIR / "bayer_raw10_packed.raw"
    packed.tofile(packed_path)
    print(f"\n已保存: output/bayer_raw10_packed.raw ({packed_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
