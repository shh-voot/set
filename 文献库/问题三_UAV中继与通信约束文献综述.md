# UAV中继节点配置与通信约束路径规划文献综述

## 概述

本文献综述针对问题三（UAV中继节点配置与通信约束下的运输路径规划）进行系统文献调研，重点关注：
1. UAV中继节点优化配置（考虑地形/DEM约束）
2. 通信感知的UAV路径规划与调度
3. 运输型与中继型UAV的联合优化
4. 通信约束下的多目标优化
5. 山地地形中的视距通信建模
6. 能量高效的中继部署策略

**文献质量要求**: SCI Q1期刊、顶级会议（IEEE INFOCOM, MobiCom, ICRA, IROS等）、2020-2024年优先

---

## 一、UAV中继节点配置优化

### 1.1 基于地理信息的3D中继定位

**[1] Joint 3-D Positioning and Power Allocation for UAV Relay Aided by Geographic Information**

- **作者**: Pengfei Yi, Liang Zhu, Lipeng Zhu, Zhenyu Xiao, Zhu Han, Xiang-Gen Xia
- **期刊**: IEEE Transactions on Wireless Communications (投稿)
- **年份**: 2021提交, 2022修订
- **DOI/链接**: [arXiv:2110.05715](https://arxiv.org/abs/2110.05715)

**核心贡献**:
- 利用三维地理信息建模建筑物遮挡效应
- 联合优化UAV 3D位置与功率分配，最大化最小用户容量
- 约束条件：链路容量、最大发射功率、遮挡约束
- 优化方法：双层优化框架
  - 外层：拉格朗日松弛获取上界乘子
  - 内层：块坐标下降(BCD) + 连续凸近似(SCA)交替优化

**与本问题的相关性**: ⭐⭐⭐⭐⭐
- 直接处理地形遮挡约束（类似DEM数据的应用）
- 3D定位优化适用于中继UAV高度与位置决策
- 多用户场景类似多个运输目标点的通信需求

---

### 1.2 基于局部地图搜索的中继配置

**[2] Efficient Local Map Search Algorithms for the Placement of Flying Relays**

- **作者**: Junting Chen, David Gesbert
- **期刊**: IEEE Transactions on Wireless Communications
- **年份**: 2018 (arXiv), 2020发表
- **DOI/链接**: [arXiv:1801.03595](https://arxiv.org/abs/1801.03595)

**核心贡献**:
- 避免统计遮挡模型，直接使用局部地形数据保证性能
- 平衡传播距离最小化与寻找有利传播条件
- 证明通过局部搜索可找到全局最优UAV位置
- 搜索轨迹长度与地理尺度线性关系，可在线实现

**算法特点**:
- 局部地图搜索（Local Map Search）
- 利用地形信息避免障碍物和阴影
- 全局最优性保证

**与本问题的相关性**: ⭐⭐⭐⭐⭐
- 直接使用地形数据（可整合DEM）
- 在线实时算法适合动态中继部署
- 全局最优保证对关键通信链路重要

---

### 1.3 城市环境3D UAV中继配置

**[3] 3D Urban UAV Relay Placement: Linear Complexity Algorithm and Analysis**

- **作者**: 相关作者（需进一步查证）
- **期刊**: IEEE Transactions on Wireless Communications
- **年份**: 2021
- **链接**: [PDF链接](http://chenjunting.org/Research/Applications/Low-altitude%20signal%20processing/21J_UAV3d_TWC.pdf)

**核心贡献**:
- 城市3D环境中的UAV中继配置
- 线性复杂度算法
- 适用于高建筑密度场景

**与本问题的相关性**: ⭐⭐⭐
- 3D配置算法可借鉴
- 城市场景与山地地形有区别但方法可迁移

---

### 1.4 元启发式优化算法

**[4] A Polynomial-Decay and Pinhole-Imaging Whale Optimization Algorithm for UAV Relay Communication Deployment**

- **作者**: 相关作者
- **期刊/会议**: arXiv预印本
- **年份**: 2026
- **链接**: [arXiv:2606.13208](https://arxiv.org/abs/2606.13208)

**核心贡献**:
- 联合优化中继UAV的位置、高度、发射功率和带宽
- 非凸、高度约束问题
- 改进的鲸鱼优化算法(Whale Optimization Algorithm)

**算法**:
- 多项式衰减策略
- 针孔成像机制
- 适合高维非凸优化

**与本问题的相关性**: ⭐⭐⭐⭐
- 元启发式方法适合多目标非凸问题
- 联合优化多个决策变量的思路可借鉴

---

## 二、通信约束下的协同路径规划

### 2.1 空地协同路径规划（经典工作）

**[5] Cooperative Routing for an Air-Ground Vehicle Team – Exact Algorithm, Transformation Method, and Heuristics**

- **作者**: Satyanarayana G. Manyam, Kaarthik Sundar, David W. Casbeer
- **期刊**: IEEE Transactions on Automation Science and Engineering
- **年份**: 2018提交, 2019发表
- **链接**: [arXiv:1804.09546](https://arxiv.org/abs/1804.09546)

**核心贡献**:
- ISR任务中地面车辆与UAV协同访问目标点
- 满足通信约束（车辆间保持通信连接）
- 混合整数线性规划(MILP)建模

**算法**:
1. **分支切割算法(Branch-and-Cut)** - 精确求解
2. **转换方法(Transformation Method)** - 问题简化
3. **启发式算法** - 大规模实例快速求解

**问题建模**:
- 决策变量：访问顺序、时间同步
- 约束：通信距离限制、任务完成约束
- 目标：最小化总任务时间

**与本问题的相关性**: ⭐⭐⭐⭐⭐
- **直接相关**：运输UAV与中继UAV的协同问题类似
- 通信约束建模可直接借鉴
- MILP建模思路适合问题三

---

### 2.2 通信约束下的空地协同（早期工作）

**[6] Path Planning for Cooperative Routing of Air-Ground Vehicles**

- **作者**: Manyam等
- **年份**: 2016
- **链接**: [arXiv:1605.09739](https://arxiv.org/abs/1605.09739)

**核心贡献**:
- 侦察任务中的协同车辆路径规划
- 通信约束维护
- 地面车辆与UAV框架

**与本问题的相关性**: ⭐⭐⭐⭐
- [5]的早期版本，核心思想类似
- 提供协同路径规划的基础框架

---

### 2.3 视距维护约束下的协同控制

**[7] Coordinated Control of Unmanned Ground Vehicle and Unmanned Aerial Vehicle Under Line-of-Sight Maintenance Constraint**

- **作者**: 相关作者
- **期刊**: Drones (MDPI)
- **年份**: 2024
- **DOI**: [链接](https://www.mdpi.com/2504-446X/10/2/151)

**核心贡献**:
- UAV前置侦察，UGV跟随的协同作战
- 视距(LoS)维护约束
- 山地和城市场景中的障碍物遮挡问题
- 非视距(NLOS)条件下的通信中断

**与本问题的相关性**: ⭐⭐⭐⭐⭐
- **直接相关**：LoS约束与DEM地形结合
- 障碍物遮挡建模适用于山地环境
- 协同控制方法可借鉴

---

### 2.4 山地环境空地协同轨迹规划

**[8] Cooperative Trajectory Planning for Air–Ground Systems in Unstructured Mountainous Environments**

- **作者**: 相关作者
- **期刊**: Symmetry (MDPI)
- **年份**: 2025
- **DOI**: [链接](https://www.mdpi.com/2073-8994/18/4/672)

**核心贡献**:
- **山地非结构化环境**中的协同轨迹规划
- 严格的车间距离约束以维护通信连通性
- 解决山地复杂地形挑战

**与本问题的相关性**: ⭐⭐⭐⭐⭐
- **直接相关**：山地环境是核心应用场景
- 通信连通性维护方法
- 复杂地形处理经验

---

