# Camera Engineering Learning

My 24-week learning project for Camera Application Engineer.

## Goals

- Camera Pipeline
- RAW / Bayer
- ISP
- OpenCV
- Camera Calibration
- CUDA
- Jetson Orin
- LibArgus
- Multi-Camera
- Performance Optimization

## Progress

| Week | Topic | Status |
| --- | --- | --- |
| 01 | Camera Pipeline / RAW / Bayer / ISP | 🔄 进行中（理论 + Bayer/RAW10 实验完成，MIPI CSI-2 待学） |
| 02 | RGB / YUV / Color Space | ⬜ |
| 03 | OpenCV Image Processing | ⬜ |
| 04 | Image Quality | ⬜ |
| 05 | BLC / DPC | ⬜ |
| 06 | LSC / Demosaic | ⬜ |
| 07 | AWB | ⬜ |
| 08 | Gamma / CCM | ⬜ |
| 09 | Noise Reduction | ⬜ |
| 10 | ISP Pipeline | ⬜ |
| 11 | Low Light | ⬜ |
| 12 | Image Quality Test | ⬜ |

Week 13–24：待补充

### 学习标准

每个 Week 都必须同时有：**理论 + 代码 + 实验结果 + 技术文档**。
只写"学习 XXX"不算完成，参考结构：

```text
weekNN/<topic>/
├── *.py            # 可运行的实验代码
├── input/          # 测试数据
├── output/         # 实验结果
└── README.md       # 算法原理 / 实现 / 结果 / 问题 / 结论
```

### Week 01 完成标准

- [x] 理解 Camera Pipeline
- [x] 理解 Image Sensor
- [x] 理解 RAW / Bayer
- [x] 理解 RGGB / BGGR / GRBG / GBRG
- [x] 实现 RGB → Bayer
- [x] 实现 Bayer → RGB
- [x] 理解 RAW8 / RAW10 / RAW12
- [x] 实现 RAW10 Packing / Unpacking
- [ ] 理解 MIPI CSI-2 在 Camera Pipeline 中的位置
- [x] 理解 ISP 的输入和输出

## 仓库结构

```text
camera-engineering-learning/
├── docs/                        # 理论学习笔记
│   └── 01_camera_pipeline.md
├── week01/
│   ├── camera_pipeline/         # Week 01 第一部分：Pipeline 截图素材
│   └── 01_bayer/                # Week 01 第二部分：Bayer / RAW10 实验
│       ├── generate_bayer.py    #   实验 1: RGB → Bayer RGGB
│       ├── generate_raw10.py    #   实验 2: 8-bit → RAW10 模拟
│       ├── raw10_packing.py     #   实验 3: RAW10 Packing / Unpacking
│       ├── demosaic.py          #   实验 4: Bayer → Demosaic → RGB
│       ├── input/               #   实验输入
│       ├── output/              #   实验结果（含对比图与字节流）
│       └── README.md
├── requirements.txt
└── README.md
```
