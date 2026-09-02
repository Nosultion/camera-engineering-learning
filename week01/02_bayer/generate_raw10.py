"""实验 2：把 8-bit Bayer 模拟成 RAW10

重要说明（写进 README 了）：
真实 Sensor 的 ADC 是直接输出 10-bit 数据（0~1023）的，
并不是"先拍 8-bit 再乘 4"。

这里的 ×4 只是为了模拟 RAW10 的数据范围，帮助理解：
  - RAW8  : 每像素 0~255
  - RAW10 : 每像素 0~1023

用法：
    python generate_raw10.py
读取 output/bayer_rggb.png，输出：
    output/raw10_unpacked.png   (uint16 PNG, 16-bit 容器存 10-bit 数据)
    output/bayer_raw10.raw      (uint16 little-endian 裸数据, 模拟 Sensor 原始输出)
"""

from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"

SCALE = 4  # 8-bit -> 10-bit 模拟系数: 0~255 -> 0~1020


def to_raw10(bayer8: np.ndarray) -> np.ndarray:
    """8-bit Bayer -> 模拟 RAW10 (uint16, 0~1020)。

    真实 Sensor 中这一步由 ADC 完成，直接量化成 10-bit。
    """
    return (bayer8.astype(np.uint16) * SCALE)


def main() -> None:
    bayer8 = cv2.imread(str(OUTPUT_DIR / "bayer_rggb.png"), cv2.IMREAD_GRAYSCALE)
    if bayer8 is None:
        raise SystemExit("找不到 output/bayer_rggb.png，请先运行 generate_bayer.py")
    h, w = bayer8.shape
    print(f"输入: bayer_rggb.png  {w}x{h}, uint8,  范围 0~255")

    raw10 = to_raw10(bayer8)
    print(f"输出: RAW10 模拟数据   {w}x{h}, uint16, 范围 {raw10.min()}~{raw10.max()}")
    print(f"示例: 128 (8-bit) -> {128*SCALE} (10-bit)")

    # 1. uint16 PNG：方便人眼看，但不是真实 Sensor 的存储方式
    cv2.imwrite(str(OUTPUT_DIR / "raw10_unpacked.png"), raw10)

    # 2. .raw 裸数据：uint16 little-endian，模拟 Sensor 直接吐出的字节流
    #    （真实 RAW10 在 MIPI 上还会再 packed 成 1.25 bytes/px，见 raw10_packing.py）
    raw_path = OUTPUT_DIR / "bayer_raw10.raw"
    raw10.tofile(raw_path)
    print(f"已保存: output/raw10_unpacked.png (uint16 PNG)")
    print(f"已保存: output/bayer_raw10.raw   ({raw_path.stat().st_size} bytes)")

    # 读回验证：字节流必须和写入前完全一致
    loaded = np.fromfile(raw_path, dtype=np.uint16).reshape(h, w)
    assert np.array_equal(loaded, raw10), "读回数据不一致！"
    print("读回验证: OK, 数据完全一致")

    print(f"\n数据量对比:")
    print(f"  8-bit Bayer (uint8)  : {w*h}     bytes ({w*h/1024:.0f} KB)")
    print(f"  RAW10 未打包 (uint16): {w*h*2}   bytes ({w*h*2/1024:.0f} KB)  <- 浪费 6 bit/像素")
    print(f"  RAW10 packed 理论值  : {w*h*10//8} bytes ({w*h*10//8/1024:.0f} KB)  <- 见 raw10_packing.py")


if __name__ == "__main__":
    main()
