#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正确的两阶段充电模型实现
符合赛题要求：SOC < 90%为快速阶段（65%时间），SOC >= 90%为慢速阶段（35%时间）
"""

def calculate_charging_time(soc_start: float, soc_target: float, t_full: float) -> float:
    """
    计算充电时间（符合赛题规则）

    Args:
        soc_start: 起始SOC [0, 1]
        soc_target: 目标SOC [0, 1]（通常为1.0）
        t_full: 等效完全充电时间（分钟）

    Returns:
        充电时间（分钟）

    赛题规则（第58行）：
    - SOC < 90%: 快速阶段，0%至90%占65%的完全充电时间
    - SOC >= 90%: 慢速阶段，90%至100%占35%的完全充电时间
    - 各阶段按SOC增量线性折算
    """
    if soc_start >= soc_target:
        return 0.0

    # 快速阶段：0% - 90%
    fast_phase_soc_range = 0.9  # 0% to 90%
    fast_phase_time_ratio = 0.65  # 65% of full time

    # 慢速阶段：90% - 100%
    slow_phase_soc_range = 0.1  # 90% to 100%
    slow_phase_time_ratio = 0.35  # 35% of full time

    total_time = 0.0

    # 情况1: 从soc_start < 90% 开始充电
    if soc_start < 0.9:
        if soc_target <= 0.9:
            # 完全在快速阶段内
            soc_delta = soc_target - soc_start
            total_time = (soc_delta / fast_phase_soc_range) * fast_phase_time_ratio * t_full
        else:
            # 跨越快速和慢速阶段
            # 快速阶段：soc_start -> 90%
            fast_soc_delta = 0.9 - soc_start
            fast_time = (fast_soc_delta / fast_phase_soc_range) * fast_phase_time_ratio * t_full

            # 慢速阶段：90% -> soc_target
            slow_soc_delta = soc_target - 0.9
            slow_time = (slow_soc_delta / slow_phase_soc_range) * slow_phase_time_ratio * t_full

            total_time = fast_time + slow_time
    else:
        # 情况2: 从soc_start >= 90% 开始充电（完全在慢速阶段）
        soc_delta = soc_target - soc_start
        total_time = (soc_delta / slow_phase_soc_range) * slow_phase_time_ratio * t_full

    return total_time


def test_charging_model():
    """测试充电模型"""
    print("="*80)
    print("两阶段充电模型测试")
    print("="*80)

    t_full = 40  # 假设完全充电时间40分钟

    test_cases = [
        (0.0, 1.0, "0% -> 100% (完全充电)"),
        (0.0, 0.9, "0% -> 90% (仅快速阶段)"),
        (0.9, 1.0, "90% -> 100% (仅慢速阶段)"),
        (0.5, 1.0, "50% -> 100% (跨两阶段)"),
        (0.2, 0.8, "20% -> 80% (快速阶段内)"),
        (0.95, 1.0, "95% -> 100% (慢速阶段内)"),
    ]

    print(f"\n等效完全充电时间: {t_full} 分钟")
    print(f"快速阶段(0-90%): {t_full * 0.65:.1f} 分钟")
    print(f"慢速阶段(90-100%): {t_full * 0.35:.1f} 分钟")

    print("\n" + "-"*80)
    print(f"{'起始SOC':<12} {'目标SOC':<12} {'充电时间':<15} {'说明':<30}")
    print("-"*80)

    for soc_start, soc_target, desc in test_cases:
        charge_time = calculate_charging_time(soc_start, soc_target, t_full)
        print(f"{soc_start*100:>5.0f}%{'':<5} {soc_target*100:>5.0f}%{'':<5} "
              f"{charge_time:>8.2f} 分钟   {desc}")

    print("\n" + "="*80)
    print("验证完全充电时间:")
    full_charge = calculate_charging_time(0.0, 1.0, t_full)
    print(f"  计算值: {full_charge:.2f} 分钟")
    print(f"  理论值: {t_full:.2f} 分钟")
    print(f"  误差: {abs(full_charge - t_full):.6f} 分钟")

    if abs(full_charge - t_full) < 0.01:
        print("  [PASS] 充电模型正确！")
    else:
        print("  [FAIL] 充电模型有误！")

    print("="*80)


if __name__ == "__main__":
    test_charging_model()
