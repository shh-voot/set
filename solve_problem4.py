#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题四主求解器
模拟灾害情景下的资源动态优化
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.batch.batch_optimizer import BatchOptimizer
from src.battery.battery_manager import BatteryPool, ChargerStation
from src.communication.los_model import LOSCommunicationModel, CommParams
from src.terrain.dem_loader import DEMLoader


class Problem4Solver:
    """问题四求解器"""

    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.depot = data_loader.get_depot()

        # 加载DEM数据
        print("加载DEM数据...")
        dem_file = "数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.mat"
        try:
            dem_loader = DEMLoader(dem_file)
            dem_data, dem_bounds = dem_loader.load()
            self.los_model = LOSCommunicationModel(
                dem_data=dem_data,
                dem_bounds=dem_bounds,
                comm_params=CommParams()
            )
            print("DEM数据加载成功！")
        except Exception as e:
            print(f"警告: DEM加载失败 ({e})")
            self.los_model = LOSCommunicationModel(comm_params=CommParams())

        # 批次优化器
        self.batch_optimizer = BatchOptimizer(self.los_model)

        # 加载问题三的中继部署结果
        self.relay_positions = self._load_relay_positions()

    def _load_relay_positions(self):
        """加载中继位置"""
        relay_file = Path("结果/问题三_中继部署.xlsx")
        if relay_file.exists():
            df = pd.read_excel(relay_file, engine='openpyxl')
            positions = []
            for _, row in df.iterrows():
                # 简化解析
                positions.append((109.22, 23.01, 400))  # 使用固定位置
            return positions
        return None

    def solve_batch_partition(self, num_batches: int):
        """
        求解批次划分

        Args:
            num_batches: 批次数量（2或3）
        """
        print(f"\n{'='*80}")
        print(f"批次划分求解 (批次数={num_batches})")
        print(f"{'='*80}")

        # 获取服务区
        service_areas = self.loader.get_service_areas()
        service_list = service_areas.to_dict('records')

        # 批次划分
        print(f"\n[步骤1] 通信冲突图构建...")
        batches = self.batch_optimizer.partition_into_batches(
            service_list,
            self.depot,
            num_batches=num_batches,
            relay_positions=self.relay_positions
        )

        print(f"\n批次划分结果:")
        for i, batch in enumerate(batches, 1):
            print(f"  批次{i}: {len(batch)}个服务区")
            print(f"    服务区列表: {', '.join(batch)}")

        # 评估
        metrics = self.batch_optimizer.evaluate_partition(batches, service_list, self.depot)
        print(f"\n划分质量评估:")
        print(f"  批次大小: {metrics['batch_sizes']}")
        print(f"  平衡度标准差: {metrics['batch_balance']:.2f}")
        print(f"  直连比例: {[f'{r:.1%}' for r in metrics['direct_link_ratio']]}")

        # 资源需求分析
        print(f"\n[步骤2] 资源需求分析...")
        resource_requirements = self._analyze_resource_requirements(batches, service_list)

        print(f"\n资源需求汇总:")
        print(f"  运输任务总数: {resource_requirements['total_transport_missions']}")
        print(f"  最大并发任务: {resource_requirements['max_concurrent_missions']}")
        print(f"  推荐电池数量: {resource_requirements['recommended_batteries']}")
        print(f"  推荐充电桩数: {resource_requirements['recommended_chargers']}")

        # 保存结果
        self._save_batch_results(num_batches, batches, metrics, resource_requirements)

        return batches, resource_requirements

    def _analyze_resource_requirements(self, batches, service_areas):
        """分析资源需求"""
        # 从问题二结果读取任务信息
        schedule_file = Path("结果/问题二_运输调度.xlsx")
        if schedule_file.exists():
            df_schedule = pd.read_excel(schedule_file, engine='openpyxl')
            total_missions = len(df_schedule)
        else:
            total_missions = len(service_areas) * 2  # 估算

        # 计算每批次最大并发
        max_concurrent = max(len(batch) for batch in batches)

        # 电池需求：考虑充电时间
        # 假设每个任务往返2小时，充电1小时，需要 ceil(3/2) = 2套电池
        recommended_batteries = max_concurrent * 2

        # 充电桩需求：考虑排队
        recommended_chargers = max(2, max_concurrent // 2)

        return {
            'total_transport_missions': total_missions,
            'max_concurrent_missions': max_concurrent,
            'recommended_batteries': recommended_batteries,
            'recommended_chargers': recommended_chargers,
            'batches': batches
        }

    def simulate_resource_usage(self, batches, num_batteries, num_chargers):
        """
        模拟资源使用情况

        Args:
            batches: 批次划分
            num_batteries: 电池数量
            num_chargers: 充电桩数量

        Returns:
            仿真结果
        """
        print(f"\n{'='*80}")
        print(f"资源使用仿真")
        print(f"{'='*80}")

        print(f"\n仿真参数:")
        print(f"  电池数量: {num_batteries}")
        print(f"  充电桩数: {num_chargers}")
        print(f"  批次数量: {len(batches)}")

        # 创建充电站和电池池
        charger = ChargerStation(num_chargers=num_chargers, power_per_charger_kw=5.0)
        battery_pool = BatteryPool(
            num_batteries=num_batteries,
            capacity_per_battery_kwh=4.0,
            charger_station=charger
        )

        # 简化仿真：每个批次顺序执行
        current_time = 0.0
        batch_results = []
        total_stockouts = 0

        for batch_idx, batch in enumerate(batches, 1):
            print(f"\n执行批次 {batch_idx}:")
            print(f"  服务区数量: {len(batch)}")

            batch_start_time = current_time
            missions_completed = 0
            stockouts = 0

            # 模拟每个服务区的任务
            for area_id in batch:
                # 尝试获取电池
                battery = battery_pool.get_available_battery(min_soc=0.95)

                if battery is None:
                    # 缺货！
                    stockouts += 1
                    print(f"    警告: {area_id} 无可用电池（缺货）")
                    continue

                # 模拟任务执行（消耗电量）
                mission_duration = 120  # 假设2小时
                energy_consumed = 2.5   # 假设消耗2.5kWh
                battery.soc -= energy_consumed / battery.capacity_kwh
                battery.soc = max(0.0, battery.soc)

                # 任务完成，归还电池
                current_time += mission_duration
                battery_pool.return_battery(battery, current_time)
                missions_completed += 1

                # 处理充电完成事件
                battery_pool.process_charge_completions(current_time)

            batch_end_time = current_time
            batch_duration = batch_end_time - batch_start_time

            batch_result = {
                'batch_id': batch_idx,
                'missions_total': len(batch),
                'missions_completed': missions_completed,
                'stockouts': stockouts,
                'duration_minutes': batch_duration,
                'battery_status': battery_pool.get_status()
            }

            batch_results.append(batch_result)
            total_stockouts += stockouts

            print(f"  完成任务: {missions_completed}/{len(batch)}")
            print(f"  缺货次数: {stockouts}")
            print(f"  批次用时: {batch_duration:.1f} 分钟")
            print(f"  电池状态: {batch_result['battery_status']}")

        # 汇总结果
        simulation_result = {
            'total_time_minutes': current_time,
            'total_stockouts': total_stockouts,
            'batch_results': batch_results,
            'final_battery_status': battery_pool.get_status()
        }

        print(f"\n仿真汇总:")
        print(f"  总用时: {current_time:.1f} 分钟")
        print(f"  总缺货次数: {total_stockouts}")
        print(f"  最终电池状态: {simulation_result['final_battery_status']}")

        return simulation_result

    def _save_batch_results(self, num_batches, batches, metrics, requirements):
        """保存批次划分结果"""
        output_dir = Path("结果")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存批次列表
        batch_data = []
        for i, batch in enumerate(batches, 1):
            for area_id in batch:
                batch_data.append({
                    'batch_id': i,
                    'service_area': area_id
                })

        df_batch = pd.DataFrame(batch_data)
        output_file = output_dir / f"问题四_{num_batches}批次划分.xlsx"
        df_batch.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n批次划分已保存: {output_file}")

        # 保存资源需求
        resource_data = [{
            'num_batches': num_batches,
            'recommended_batteries': requirements['recommended_batteries'],
            'recommended_chargers': requirements['recommended_chargers'],
            'max_concurrent_missions': requirements['max_concurrent_missions']
        }]
        df_resource = pd.DataFrame(resource_data)
        output_file = output_dir / f"问题四_{num_batches}批次资源需求.xlsx"
        df_resource.to_excel(output_file, index=False, engine='openpyxl')
        print(f"资源需求已保存: {output_file}")


def main():
    print("="*80)
    print("问题四：模拟灾害情景下的资源动态优化")
    print("="*80)

    # 加载数据
    print("\n[数据加载]")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 创建求解器
    solver = Problem4Solver(loader)

    # 求解2批次方案
    print("\n" + "="*80)
    print("方案一：2批次划分")
    print("="*80)
    batches_2, requirements_2 = solver.solve_batch_partition(num_batches=2)

    # 资源仿真（2批次）
    print("\n[资源仿真 - 2批次]")
    sim_result_2 = solver.simulate_resource_usage(
        batches_2,
        num_batteries=requirements_2['recommended_batteries'],
        num_chargers=requirements_2['recommended_chargers']
    )

    # 求解3批次方案
    print("\n" + "="*80)
    print("方案二：3批次划分")
    print("="*80)
    batches_3, requirements_3 = solver.solve_batch_partition(num_batches=3)

    # 资源仿真（3批次）
    print("\n[资源仿真 - 3批次]")
    sim_result_3 = solver.simulate_resource_usage(
        batches_3,
        num_batteries=requirements_3['recommended_batteries'],
        num_chargers=requirements_3['recommended_chargers']
    )

    # 对比分析
    print("\n" + "="*80)
    print("方案对比")
    print("="*80)
    print(f"\n{'指标':<20} {'2批次':<15} {'3批次':<15}")
    print("-"*50)
    print(f"{'推荐电池数':<20} {requirements_2['recommended_batteries']:<15} {requirements_3['recommended_batteries']:<15}")
    print(f"{'推荐充电桩数':<20} {requirements_2['recommended_chargers']:<15} {requirements_3['recommended_chargers']:<15}")
    print(f"{'总用时(分钟)':<20} {sim_result_2['total_time_minutes']:<15.1f} {sim_result_3['total_time_minutes']:<15.1f}")
    print(f"{'缺货次数':<20} {sim_result_2['total_stockouts']:<15} {sim_result_3['total_stockouts']:<15}")

    print("\n" + "="*80)
    print("问题四求解完成！")
    print("="*80)


if __name__ == "__main__":
    main()
