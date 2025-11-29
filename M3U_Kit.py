#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U播放列表处理工具（简化版）
用于合并多个目录中的同名文件（txt和m3u），并进行去重、标准化和分组
"""

import re
import argparse
import sys
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load(config_file: str) -> Tuple[Dict, Dict, Dict]:
        """
        加载配置文件
        
        Returns:
            (channel_categories, channel_mapping, alias_map) 元组
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        local_vars = {}
        exec(content, {}, local_vars)
        
        channel_categories = local_vars.get('CHANNEL_CATEGORIES', {})
        channel_mapping = local_vars.get('CHANNEL_MAPPING', {})
        
        # 构建别名到标准名的映射
        alias_map = {}
        for standard_name, aliases in channel_mapping.items():
            alias_map[standard_name] = standard_name
            for alias in aliases:
                alias_map[alias] = standard_name
        
        return channel_categories, channel_mapping, alias_map


class FileParser:
    """文件解析器"""
    
    @staticmethod
    def parse_txt(file_path: Path) -> List[Dict[str, str]]:
        """
        解析txt文件（CSV格式：第一列tvg-name，第二列url）
        
        Returns:
            频道列表
        """
        channels = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',', 1)
                if len(parts) >= 2:
                    tvg_name = parts[0].strip()
                    url = parts[1].strip()
                    # 忽略以 # 开头的 URL
                    if url.startswith('#'):
                        continue
                    if tvg_name and url:
                        # 检查 URL 是否包含 # 分隔的两个 URL
                        if '#' in url:
                            url_parts = url.split('#', 1)
                            first_url = url_parts[0].strip()
                            second_url = url_parts[1].strip()
                            
                            # 检查第二个部分是否也是 URL 格式
                            url_prefixes = ['rtp://', 'udp://', 'http://', 'https://']
                            if any(second_url.startswith(prefix) for prefix in url_prefixes):
                                # 拆分为两条记录
                                channels.append({
                                    'tvg-name': tvg_name,
                                    'url': first_url,
                                    'tvg-logo': '',
                                    'group-title': '',
                                    'channel-name': tvg_name
                                })
                                channels.append({
                                    'tvg-name': tvg_name,
                                    'url': second_url,
                                    'tvg-logo': '',
                                    'group-title': '',
                                    'channel-name': tvg_name
                                })
                            else:
                                # 如果第二个部分不是 URL，只使用第一个部分
                                channels.append({
                                    'tvg-name': tvg_name,
                                    'url': first_url,
                                    'tvg-logo': '',
                                    'group-title': '',
                                    'channel-name': tvg_name
                                })
                        else:
                            # 普通 URL，直接添加
                            channels.append({
                                'tvg-name': tvg_name,
                                'url': url,
                                'tvg-logo': '',
                                'group-title': '',
                                'channel-name': tvg_name
                            })
        return channels
    
    @staticmethod
    def parse_m3u(file_path: Path) -> List[Dict[str, str]]:
        """
        解析M3U文件（兼容简单格式和完整格式）
        
        Returns:
            频道列表
        """
        channels = []
        current_channel = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # 跳过文件头
                if line.startswith('#EXTM3U'):
                    continue
                
                # 解析 #EXTINF 行
                if line.startswith('#EXTINF'):
                    current_channel = FileParser._parse_extinf(line)
                    continue
                
                # URL行
                if current_channel and FileParser._is_url(line):
                    current_channel['url'] = line
                    channels.append(current_channel)
                    current_channel = None
        
        return channels
    
    @staticmethod
    def _parse_extinf(line: str) -> Dict[str, str]:
        """解析 #EXTINF 行"""
        channel = {
            'tvg-name': '',
            'tvg-logo': '',
            'group-title': '',
            'url': '',
            'channel-name': ''
        }
        
        # 提取属性
        attrs = {
            'tvg-id': r'tvg-id="([^"]*)"',
            'tvg-name': r'tvg-name="([^"]*)"',
            'tvg-logo': r'tvg-logo="([^"]*)"',
            'group-title': r'group-title="([^"]*)"'
        }
        
        for key, pattern in attrs.items():
            match = re.search(pattern, line)
            if match:
                channel[key] = match.group(1)
        
        # 提取频道名称（最后一个逗号后的内容）
        parts = line.split(',')
        if len(parts) > 1:
            channel['channel-name'] = parts[-1].strip()
        
        # 如果tvg-name为空，使用channel-name
        if not channel['tvg-name'] and channel['channel-name']:
            channel['tvg-name'] = channel['channel-name']
        
        return channel
    
    @staticmethod
    def _is_url(line: str) -> bool:
        """判断是否为URL行"""
        return any(line.startswith(prefix) for prefix in 
                  ['http://', 'https://', 'rtp://', 'udp://'])


class ChannelProcessor:
    """频道处理器"""
    
    def __init__(self, config_file: str):
        """初始化处理器"""
        self.channel_categories, self.channel_mapping, self.alias_map = ConfigLoader.load(config_file)
    
    def normalize_name(self, name: str) -> str:
        """标准化频道名称"""
        return self.alias_map.get(name, name)
    
    def find_group_title(self, channel_name: str) -> str:
        """查找分组"""
        for group_title, channels in self.channel_categories.items():
            if channel_name in channels:
                return group_title
        return '其他'
    
    def try_get_logo_url(self, tvg_name: str) -> Optional[str]:
        """
        尝试从两个 URL 获取 logo
        
        Args:
            tvg_name: 频道名称（tvg-name）
            
        Returns:
            如果找到可访问的 logo URL，返回 URL；否则返回 None
        """
        if not tvg_name:
            return None
        
        # 两个 logo URL 模板
        logo_urls = [
            f"https://epg.112114.xyz/logo/{tvg_name}.png",
            f"https://live.fanmingming.com/tv/{tvg_name}.png"
        ]
        
        # 尝试每个 URL
        for logo_url in logo_urls:
            if self._check_url_exists(logo_url):
                return logo_url
        
        return None
    
    def _check_url_exists(self, url: str, timeout: int = 5) -> bool:
        """检查 URL 是否可以访问"""
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                return True
        except:
            pass
        
        try:
            response = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
            response.close()
            return response.status_code == 200
        except:
            return False
    
    def process_channels(self, channels: List[Dict]) -> List[Dict]:
        """
        处理频道列表：标准化名称、分组、补全logo、URL去重
        
        Args:
            channels: 原始频道列表
            
        Returns:
            处理后的频道列表
        """
        # 1. 标准化名称和分组
        for channel in channels:
            tvg_name = channel.get('tvg-name', '')
            if tvg_name:
                standard_name = self.normalize_name(tvg_name)
                channel['tvg-name'] = standard_name
                if not channel.get('channel-name'):
                    channel['channel-name'] = standard_name
                
                # 设置分组
                if not channel.get('group-title'):
                    channel['group-title'] = self.find_group_title(standard_name)
        
        # 2. URL去重（保留第一个出现的，优先保留有logo的）
        seen_urls = {}
        deduplicated = []
        
        for channel in channels:
            url = channel.get('url', '')
            if not url:
                continue
            
            if url not in seen_urls:
                seen_urls[url] = channel
                deduplicated.append(channel)
            else:
                # 重复URL，优先保留有logo的
                existing = seen_urls[url]
                if not existing.get('tvg-logo') and channel.get('tvg-logo'):
                    # 替换为有logo的频道
                    idx = deduplicated.index(existing)
                    deduplicated[idx] = channel
                    seen_urls[url] = channel
        
        # 3. 补全缺失的logo
        for channel in deduplicated:
            if not channel.get('tvg-logo'):
                tvg_name = channel.get('tvg-name', '')
                if tvg_name:
                    logo_url = self.try_get_logo_url(tvg_name)
                    if logo_url:
                        channel['tvg-logo'] = logo_url
        
        # 4. 重新编号
        for idx, channel in enumerate(deduplicated, 1):
            channel['tvg-id'] = str(idx)
        
        return deduplicated


def merge_directories(input_dirs: List[str], output_dir: str, config_file: str, convert_txt_to_m3u: bool = False):
    """
    合并多个目录中的同名文件（只处理所有目录中都存在的文件）
    
    Args:
        input_dirs: 输入目录列表
        output_dir: 输出目录
        config_file: 配置文件路径
        convert_txt_to_m3u: 如果为True，将dir1中存在的txt但dir2中不存在的m3u转换为m3u
    """
    input_paths = [Path(d) for d in input_dirs]
    output_path = Path(output_dir)
    
    # 验证输入目录
    for path in input_paths:
        if not path.exists():
            raise FileNotFoundError(f"输入目录不存在: {path}")
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 收集每个目录中的文件（按文件名分组）
    dir_file_sets = []
    for input_path in input_paths:
        file_set = set()
        # 查找txt和m3u文件
        for txt_file in input_path.glob("*.txt"):
            file_set.add(txt_file.stem)
        for m3u_file in input_path.glob("*.m3u"):
            file_set.add(m3u_file.stem)
        dir_file_sets.append(file_set)
    
    # 初始化处理器
    processor = ChannelProcessor(config_file)
    
    # 如果启用了 convert_txt_to_m3u 选项，处理第一个目录中独有的 txt 文件
    converted_count = 0
    if convert_txt_to_m3u and len(input_paths) >= 2:
        first_dir = input_paths[0]
        second_dir = input_paths[1]
        
        # 获取第二个目录中的 m3u 文件名集合
        second_dir_m3u_files = {f.stem for f in second_dir.glob("*.m3u")}
        
        # 查找第一个目录中的 txt 文件，但第二个目录中没有对应 m3u 的
        for txt_file in first_dir.glob("*.txt"):
            file_name = txt_file.stem
            if file_name not in second_dir_m3u_files:
                print(f"🔄 转换: {txt_file.name} -> {file_name}.m3u")
                try:
                    # 解析 txt 文件
                    channels = FileParser.parse_txt(txt_file)
                    if channels:
                        # 处理频道（标准化、分组、补全logo）
                        processed_channels = processor.process_channels(channels)
                        
                        # 生成输出文件
                        output_file = output_path / f"{file_name}.m3u"
                        generate_m3u_file(output_file, file_name, processed_channels)
                        
                        converted_count += 1
                        print(f"  ✅ 转换完成: {len(processed_channels)} 个频道")
                    else:
                        print(f"  ⚠️  未找到任何频道，跳过")
                except Exception as e:
                    print(f"  ❌ 转换失败: {e}")
        
        if converted_count > 0:
            print(f"\n📊 共转换 {converted_count} 个 txt 文件为 m3u 文件\n")
    
    # 找出所有目录中都存在的文件名（交集）
    if len(dir_file_sets) == 0:
        print("❌ 未找到任何输入目录")
        return
    
    common_files = dir_file_sets[0]
    for file_set in dir_file_sets[1:]:
        common_files = common_files & file_set
    
    if not common_files:
        print("⚠️  未找到任何在所有目录中都存在的文件")
        if not convert_txt_to_m3u or converted_count == 0:
            return
        else:
            print("✅ 已完成的转换操作")
            return
    
    # 收集需要合并的文件
    file_groups = defaultdict(list)
    for file_name in common_files:
        for input_path in input_paths:
            # 查找txt文件
            txt_file = input_path / f"{file_name}.txt"
            if txt_file.exists():
                file_groups[file_name].append(txt_file)
            # 查找m3u文件
            m3u_file = input_path / f"{file_name}.m3u"
            if m3u_file.exists():
                file_groups[file_name].append(m3u_file)
    
    print(f"📋 找到 {len(common_files)} 个文件在所有目录中都存在，将进行合并")
    print(f"📁 输出目录: {output_path}\n")
    
    # 处理每个文件组
    for file_name, files in sorted(file_groups.items()):
        print(f"🔄 正在处理: {file_name}")
        
        all_channels = []
        
        # 解析所有同名文件
        for file_path in files:
            print(f"  📄 解析: {file_path.name}")
            try:
                if file_path.suffix == '.txt':
                    channels = FileParser.parse_txt(file_path)
                elif file_path.suffix == '.m3u':
                    channels = FileParser.parse_m3u(file_path)
                else:
                    continue
                
                all_channels.extend(channels)
                print(f"    找到 {len(channels)} 个频道")
            except Exception as e:
                print(f"    ❌ 解析失败: {e}")
                continue
        
        if not all_channels:
            print(f"  ⚠️  未找到任何频道，跳过\n")
            continue
        
        # 处理频道（标准化、去重、补全logo）
        print(f"  🔧 处理频道（合并前: {len(all_channels)} 个）...")
        processed_channels = processor.process_channels(all_channels)
        print(f"  ✅ 处理完成（合并后: {len(processed_channels)} 个）")
        
        # 生成输出文件
        output_file = output_path / f"{file_name}.m3u"
        generate_m3u_file(output_file, file_name, processed_channels)
        
        print(f"  💾 已保存: {output_file}\n")
    
    print(f"✅ 全部完成！")


def generate_m3u_file(output_path: Path, file_name: str, channels: List[Dict]):
    """
    生成M3U文件
    
    Args:
        output_path: 输出文件路径
        file_name: 文件名（用于文件头）
        channels: 频道列表
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        # 写入文件头
        f.write(f'#EXTM3U name="{file_name}"\n')
        f.write(f'#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml,http://epg.51zmt.top:8000/e.xml"\n')
        
        # 写入频道
        for channel in channels:
            # 构建 #EXTINF 行
            duration = channel.get('duration', '-1')
            extinf = f'#EXTINF:{duration}'
            
            attrs = []
            for key in ['tvg-id', 'tvg-name', 'tvg-logo', 'group-title']:
                if channel.get(key):
                    attrs.append(f'{key}="{channel[key]}"')
            
            if attrs:
                extinf += ' ' + ' '.join(attrs)
            
            channel_name = channel.get('channel-name', channel.get('tvg-name', ''))
            if channel_name:
                extinf += f',{channel_name}'
            
            f.write(extinf + '\n')
            f.write(channel.get('url', '') + '\n')


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='M3U播放列表处理工具（简化版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 合并多个目录中的同名文件
  %(prog)s --input-dir dir1 --input-dir dir2 --output-dir output --config data.py
        """
    )
    
    parser.add_argument('--input-dir', action='append', required=True,
                       help='输入目录（可多次指定）')
    parser.add_argument('--output-dir', required=True,
                       help='输出目录')
    parser.add_argument('--config', default='data.py',
                       help='配置文件路径（默认：data.py）')
    parser.add_argument('--convert-txt-to-m3u', action='store_true',
                       help='将第一个目录中存在的txt文件（但第二个目录中不存在对应m3u）转换为m3u文件')
    
    args = parser.parse_args()
    
    try:
        merge_directories(args.input_dir, args.output_dir, args.config, args.convert_txt_to_m3u)
    except Exception as e:
        print(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
