# Camera Pipeline

> Week 01 学习笔记：帮助刚入门 Camera Engineering 的软件工程师建立整体认知。

## 1. Camera Pipeline 是什么

Camera Pipeline（相机管线）是指光线进入相机到最终输出图像所经过的一整条数据链路：

```text
Light
  ↓
Lens
  ↓
Image Sensor
  ↓
RAW
  ↓
ISP
  ↓
RGB / YUV
  ↓
Application
```

- Light：现实世界的光线
- Lens：镜头，把光线聚焦到传感器上
- Image Sensor：图像传感器，把光信号转成电信号，输出 RAW 数据
- ISP：对 RAW 做一系列图像处理
- RGB / YUV：处理后得到的、可以正常观看和使用的图像
- Application：显示、保存，或交给后续算法（检测、识别等）

理解这条链路，就建立了 Camera Engineering 的整体骨架。

## 2. Image Sensor 做了什么

- Sensor 感受光线：光线经过镜头投射到传感器表面
- 光子 → 电信号：传感器把接收到的光转换成电信号
- 数字化：电信号经过模数转换，最终输出数字化的 RAW 数据
- 注意：Sensor 输出的并不是我们平时看到的"正常 RGB 图片"，而是 RAW

（这里不深入 Sensor 内部的物理原理，知道"光 → 电信号 → 数字 RAW"即可。）

## 3. RAW 是什么

- RAW 是 Sensor 输出的原始图像数据（raw image data）
- RAW 不等于普通 RGB 图片：它还不能直接给人看
- 常见 bit depth：RAW8 / RAW10 / RAW12 / RAW14（数字越大，每个像素的位置越深、信息越多）

关键点：在 Bayer RAW 中，一个像素位置通常只采集 R / G / B 中的一种颜色信息。

一个简单的 Bayer RAW 排列示例：

```text
R G R G
G B G B
R G R G
G B G B
```

也就是说：一个 RAW pixel 通常不是完整的 RGB 三通道。

## 4. Bayer / CFA

- CFA：Color Filter Array，颜色滤光阵列
- 位置：Sensor 像素前面的一层颜色滤光片
- 作用：让每个像素只接收一种颜色的光（R、G 或 B）
- 常见排列：Bayer Pattern（拜耳排列）
- RGGB、BGGR 等只是 Bayer Pattern 的不同排列方式（起始位置 / 顺序不同）

（这里不深入数学推导。）

## 5. ISP 是什么

ISP = Image Signal Processor（图像信号处理器）。

核心作用：把 Sensor 输出的 RAW 数据，经过一系列图像处理，变成更适合显示、保存或后续算法处理的图像。

典型的 ISP 处理链路：

```text
RAW
  ↓
BLC
  ↓
DPC
  ↓
LSC
  ↓
Denoise
  ↓
AWB
  ↓
Demosaic
  ↓
CCM
  ↓
Gamma
  ↓
RGB / YUV
```

各模块一句话说明：

- BLC：Black Level Correction，黑电平校正
- DPC：Defective Pixel Correction，坏点校正
- LSC：Lens Shading Correction，镜头阴影 / 暗角校正
- Denoise：降噪
- AWB：Auto White Balance，自动白平衡
- Demosaic：根据 Bayer RAW 重建 RGB 三通道图像
- CCM：Color Correction Matrix，颜色校正
- Gamma：调整图像亮度 / 色调响应

（这里不涉及复杂数学公式。）

## 6. RAW → RGB 到底发生了什么

```text
RAW
  ↓
ISP
  ↓
RGB
```

- RAW 中一个像素位置通常只有一个颜色采样（R / G / B 之一），因此不能直接当作完整的 RGB 图片
- ISP 需要依次完成：
  - 黑电平校正（BLC）
  - 坏点处理（DPC）
  - 镜头校正（LSC）
  - 降噪（Denoise）
  - 白平衡（AWB）
  - Demosaic（重建 RGB 三通道）
  - 颜色校正（CCM）
  - Gamma
- 经过这些处理后，才形成可以正常显示和使用的 RGB 图像

## 7. Camera Pipeline 总结

```text
Light
  ↓
Lens
  ↓
Image Sensor
  ↓
MIPI CSI-2
  ↓
RAW Bayer
  ↓
ISP
  ↓
RGB / YUV
  ↓
Application
```

注意：MIPI CSI-2 是 Sensor 与处理器之间的数据传输接口，不是 ISP 的一部分。

## 8. 今天暂时不深入

- Demosaic 数学算法
- AWB 数学计算
- CCM 矩阵计算
- Gamma 公式
- Noise Model
- HDR 算法
- ISP 各模块具体实现

这些内容在后续学习中逐步深入。

## 9. 我的理解 / 学习总结

- 我今天理解了什么：
  - （待补充）
- 我还不理解什么：
  - （待补充）
