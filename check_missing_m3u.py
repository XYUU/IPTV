#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 m3u 目录下缺失的省市运营商文件
"""

import os
import re
from pathlib import Path
from typing import Set, List, Tuple

# 三大运营商
OPERATORS = ["移动", "联通", "电信"]

# 从 TODO.md 读取省市列表
def read_provinces_from_todo(todo_file: str = "TODO.md") -> List[str]:
    """从 TODO.md 文件的 284-315 行读取省市列表"""
    provinces = []
    try:
        with open(todo_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 读取 284-315 行（索引从0开始，所以是 283-314）
            for i in range(283, min(315, len(lines))):
                line = lines[i].strip()
                # 提取引号中的省市名称
                match = re.search(r'"([^"]+)"', line)
                if match:
                    provinces.append(match.group(1))
    except FileNotFoundError:
        print(f"错误：找不到文件 {todo_file}")
    except Exception as e:
        print(f"读取文件时出错：{e}")
    
    return provinces

# 获取 m3u 目录下所有文件
def get_existing_files(m3u_dir: str = "data/m3ukit/m3u") -> Set[str]:
    """获取 m3u 目录下所有 .m3u 文件名（不含路径和扩展名）"""
    existing = set()
    m3u_path = Path(m3u_dir)
    
    if not m3u_path.exists():
        print(f"警告：目录 {m3u_dir} 不存在")
        return existing
    
    for file in m3u_path.glob("*.m3u"):
        # 去掉扩展名
        filename = file.stem
        existing.add(filename)
    
    return existing

# 解析文件名，提取省市和运营商
def parse_filename(filename: str) -> Tuple[str, str]:
    """从文件名中提取省市和运营商
    返回: (省市, 运营商) 或 (None, None) 如果无法解析
    """
    for operator in OPERATORS:
        if filename.endswith(operator):
            province = filename[:-len(operator)]
            return province, operator
    return None, None

# 检查缺失的文件
def check_missing_files(provinces: List[str], existing_files: Set[str]) -> List[Tuple[str, str]]:
    """检查缺失的省市运营商文件
    返回: [(省市, 运营商), ...] 缺失的文件列表
    """
    missing = []
    
    # 构建期望的文件集合
    expected_files = set()
    for province in provinces:
        for operator in OPERATORS:
            expected_files.add(f"{province}{operator}")
    
    # 检查每个期望的文件是否存在
    for province in provinces:
        for operator in OPERATORS:
            filename = f"{province}{operator}"
            if filename not in existing_files:
                missing.append((province, operator))
    
    return missing

# 主函数
def main():
    print("=" * 60)
    print("检查 m3u 目录下缺失的省市运营商文件")
    print("=" * 60)
    print()
    
    # 读取省市列表
    print("正在从 TODO.md 读取省市列表...")
    provinces = read_provinces_from_todo()
    print(f"找到 {len(provinces)} 个省市")
    print(f"省市列表: {', '.join(provinces)}")
    print()
    
    # 获取现有文件
    print("正在扫描 m3u 目录...")
    existing_files = get_existing_files()
    print(f"找到 {len(existing_files)} 个 .m3u 文件")
    print()
    
    # 检查缺失的文件
    print("正在检查缺失的文件...")
    missing = check_missing_files(provinces, existing_files)
    
    # 输出结果
    print("=" * 60)
    if missing:
        print(f"发现 {len(missing)} 个缺失的文件：")
        print()
        
        # 按省市分组显示
        missing_by_province = {}
        for province, operator in missing:
            if province not in missing_by_province:
                missing_by_province[province] = []
            missing_by_province[province].append(operator)
        
        for province in sorted(missing_by_province.keys()):
            operators = missing_by_province[province]
            print(f"  {province}: 缺少 {', '.join(operators)}")
            for operator in operators:
                print(f"    - {province}{operator}.m3u")
        
        print()
        print("=" * 60)
        print("详细缺失列表（按省市排序）：")
        for province, operator in sorted(missing):
            print(f"  {province}{operator}.m3u")
    else:
        print("✓ 所有省市都有完整的三大运营商文件！")
    
    print()
    print("=" * 60)
    
    # 统计信息
    total_expected = len(provinces) * len(OPERATORS)
    total_existing = len(existing_files)
    total_missing = len(missing)
    coverage = ((total_expected - total_missing) / total_expected * 100) if total_expected > 0 else 0
    
    print("统计信息：")
    print(f"  期望文件数: {total_expected}")
    print(f"  现有文件数: {total_existing}")
    print(f"  缺失文件数: {total_missing}")
    print(f"  完成度: {coverage:.1f}%")
    print("=" * 60)

if __name__ == "__main__":
    main()

