#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U播放列表处理工具
用于解析、合并、比较和导出M3U播放列表文件
"""

import re
import json
import csv
import argparse
import sys
import requests
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
from urllib.parse import quote


class ChannelConfigLoader:
    """频道配置加载器"""
    
    @staticmethod
    def load(config_file: str) -> Tuple[Dict, Dict, Dict]:
        """
        加载配置文件中的CHANNEL_CATEGORIES和CHANNEL_MAPPING
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            (channel_categories, channel_mapping, alias_map) 元组
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        local_vars = {}
        
        # 处理包含 data 模块导入的情况
        if 'from data import' in content or 'import data' in content:
            data_file = config_path.parent / 'data.py'
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as df:
                    data_content = df.read()
                exec(data_content, {}, local_vars)
                exec(content, local_vars, local_vars)
            else:
                import sys
                sys.path.insert(0, str(config_path.parent))
                exec(content, {}, local_vars)
        else:
            exec(content, {}, local_vars)
        
        channel_categories = local_vars.get('CHANNEL_CATEGORIES', {})
        channel_mapping = local_vars.get('CHANNEL_MAPPING', {})
        
        # 构建别名到标准名的映射
        alias_map = ChannelConfigLoader._build_alias_map(channel_mapping)
        
        return channel_categories, channel_mapping, alias_map
    
    @staticmethod
    def _build_alias_map(channel_mapping: Dict) -> Dict[str, str]:
        """构建别名到标准名的映射"""
        alias_map = {}
        for standard_name, aliases in channel_mapping.items():
            for alias in aliases:
                alias_map[alias] = standard_name
            alias_map[standard_name] = standard_name
        return alias_map


class RTPFileLoader:
    """RTP文件加载器"""
    
    @staticmethod
    def load(rtp_path: Path) -> Dict[str, List[str]]:
        """
        加载RTP文件，返回频道名到RTP URL列表的映射
        
        Args:
            rtp_path: RTP文件路径
            
        Returns:
            频道名到URL列表的字典
        """
        rtp_channels = defaultdict(list)
        
        with open(rtp_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or ',' not in line:
                    continue
                
                parts = line.split(',', 1)
                if len(parts) == 2:
                    ch_name = parts[0].strip()
                    rtp_url = parts[1].strip()
                    rtp_channels[ch_name].append(rtp_url)
        
        return dict(rtp_channels)


class ChannelMapper:
    """频道名称映射器"""
    
    def __init__(self, channel_mapping: Dict, channel_categories: Dict):
        """
        初始化映射器
        
        Args:
            channel_mapping: 频道映射配置
            channel_categories: 频道分类配置
        """
        self.channel_mapping = channel_mapping
        self.channel_categories = channel_categories
        self.name_to_standard = ChannelConfigLoader._build_alias_map(channel_mapping)
    
    def normalize_name(self, name: str) -> str:
        """将频道名标准化"""
        return self.name_to_standard.get(name, name)
    
    def find_group_title(self, channel_name: str) -> str:
        """根据频道名称查找对应的分组"""
        for group_title, channels in self.channel_categories.items():
            if channel_name in channels:
                return group_title
        return '其他'
    
    def build_rtp_mapping(self, rtp_channels: Dict[str, List[str]]) -> Tuple[Dict, Dict]:
        """
        构建RTP频道名到标准名的映射
        
        Args:
            rtp_channels: RTP频道字典
            
        Returns:
            (rtp_to_standard, standard_to_rtp) 元组
        """
        rtp_to_standard = {}
        for rtp_name in rtp_channels.keys():
            standard = self.normalize_name(rtp_name)
            rtp_to_standard[rtp_name] = standard
        
        standard_to_rtp = defaultdict(list)
        for rtp_name, standard in rtp_to_standard.items():
            standard_to_rtp[standard].append(rtp_name)
        
        return rtp_to_standard, dict(standard_to_rtp)


class M3UPlaylist:
    """M3U播放列表处理器"""
    
    def __init__(self, file_path: str):
        """
        初始化播放列表处理器
        
        Args:
            file_path: M3U文件路径
        """
        self.file_path = Path(file_path)
        self.channels: List[Dict[str, str]] = []
        self.header_info: Dict[str, str] = {}
    
    def parse(self) -> List[Dict[str, str]]:
        """
        解析M3U文件
        
        Returns:
            频道信息列表
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_channel: Optional[Dict[str, str]] = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('#EXTM3U'):
                self._parse_header(line)
                continue
            
            if line.startswith('#EXTINF'):
                current_channel = self._parse_extinf(line)
                continue
            
            if self._is_url_line(line):
                if current_channel:
                    current_channel['url'] = line
                    self.channels.append(current_channel)
                    current_channel = None
        
        return self.channels
    
    def _is_url_line(self, line: str) -> bool:
        """判断是否为URL行"""
        return any(line.startswith(prefix) for prefix in 
                  ['http://', 'https://', 'rtp://', 'udp://'])
    
    def _parse_header(self, line: str):
        """解析M3U文件头"""
        name_match = re.search(r'name="([^"]+)"', line)
        if name_match:
            self.header_info['name'] = name_match.group(1)
        
        tvg_url_match = re.search(r'x-tvg-url="([^"]+)"', line)
        if tvg_url_match:
            self.header_info['x-tvg-url'] = tvg_url_match.group(1)
    
    def _parse_extinf(self, line: str) -> Dict[str, str]:
        """解析 #EXTINF 行"""
        channel = {}
        
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
        
        # 提取时长
        duration_match = re.match(r'#EXTINF:(-?\d+)', line)
        if duration_match:
            channel['duration'] = duration_match.group(1)
        
        return channel
    
    def merge_with_rtp(self, rtp_file_path: str, 
                      rtp_dir: str = "source/zubo/rtp",
                      config_file: str = "source/zubo/data.py",
                      filter_only: bool = False) -> List[Dict[str, str]]:
        """
        使用RTP文件替换M3U中的链接，并重新组织频道信息
        
        Args:
            rtp_file_path: RTP文件路径（相对于rtp_dir）
            rtp_dir: RTP文件目录
            config_file: 配置文件路径
            filter_only: 如果为True，只保留RTP文件中存在的频道（删除模板中没有的频道）
            
        Returns:
            重新组织后的频道列表
        """
        # 加载配置和RTP文件
        channel_categories, channel_mapping, _ = ChannelConfigLoader.load(config_file)
        mapper = ChannelMapper(channel_mapping, channel_categories)
        
        rtp_path = Path(rtp_dir) / rtp_file_path
        if not rtp_path.exists():
            raise FileNotFoundError(f"RTP文件不存在: {rtp_path}")
        
        rtp_channels = RTPFileLoader.load(rtp_path)
        rtp_to_standard, standard_to_rtp = mapper.build_rtp_mapping(rtp_channels)
        
        # 处理现有频道
        processed_channels = []
        matched_rtp_names = set()
        
        for channel in self.channels:
            new_channel = self._process_channel_with_rtp(
                channel, mapper, rtp_channels, rtp_to_standard, 
                standard_to_rtp, matched_rtp_names
            )
            
            # 如果filter_only为True，只保留匹配的频道（有URL且URL来自RTP文件）
            if filter_only:
                if new_channel and new_channel.get('url'):
                    # 检查是否成功匹配到RTP频道（matched_rtp_names中有记录）
                    tvg_name = channel.get('tvg-name') or channel.get('channel-name', '')
                    standard_name = mapper.normalize_name(tvg_name)
                    
                    # 检查是否匹配成功
                    is_matched = False
                    if standard_name in standard_to_rtp:
                        is_matched = True
                    elif standard_name in rtp_channels:
                        is_matched = True
                    elif tvg_name in rtp_channels:
                        is_matched = True
                    
                    if is_matched:
                        processed_channels.append(new_channel)
            else:
                if new_channel:
                    processed_channels.append(new_channel)
        
        # 添加未匹配的RTP频道（仅在非过滤模式下）
        if not filter_only:
            unmatched_rtp = set(rtp_channels.keys()) - matched_rtp_names
            for rtp_name in unmatched_rtp:
                standard_name = rtp_to_standard.get(rtp_name, rtp_name)
                new_channel = {
                    'tvg-name': standard_name,
                    'tvg-logo': '',
                    'group-title': mapper.find_group_title(standard_name),
                    'channel-name': standard_name,
                    'url': rtp_channels[rtp_name][0],
                    'duration': '-1'
                }
                processed_channels.append(new_channel)
        
        # 去除重复的URL（保留第一个出现的，优先保留有logo的）
        seen_urls = {}
        deduplicated_channels = []
        
        for channel in processed_channels:
            url = channel.get('url', '')
            if not url:
                continue
            
            if url not in seen_urls:
                # 第一次出现，直接添加
                seen_urls[url] = channel
                deduplicated_channels.append(channel)
            else:
                # 重复URL，优先保留有logo的频道
                existing = seen_urls[url]
                if not existing.get('tvg-logo') and channel.get('tvg-logo'):
                    # 替换为有logo的频道
                    idx = deduplicated_channels.index(existing)
                    deduplicated_channels[idx] = channel
                    seen_urls[url] = channel
        
        # 重新编号
        for idx, channel in enumerate(deduplicated_channels, 1):
            channel['tvg-id'] = str(idx)
        
        self.channels = deduplicated_channels
        return deduplicated_channels
    
    def _process_channel_with_rtp(self, channel: Dict, mapper: ChannelMapper,
                                  rtp_channels: Dict, rtp_to_standard: Dict,
                                  standard_to_rtp: Dict, matched_rtp_names: Set) -> Optional[Dict]:
        """处理单个频道与RTP的匹配"""
        tvg_name = channel.get('tvg-name') or channel.get('channel-name', '')
        standard_name = mapper.normalize_name(tvg_name)
        
        # 查找匹配的RTP频道
        matched_rtp = None
        matched_rtp_key = None
        
        if standard_name in standard_to_rtp:
            rtp_key = standard_to_rtp[standard_name][0]
            matched_rtp = rtp_channels[rtp_key]
            matched_rtp_key = rtp_key
            matched_rtp_names.add(rtp_key)
        elif standard_name in rtp_channels:
            matched_rtp = rtp_channels[standard_name]
            matched_rtp_key = standard_name
            matched_rtp_names.add(standard_name)
        else:
            # 尝试直接匹配原始名称
            if tvg_name in rtp_channels:
                matched_rtp = rtp_channels[tvg_name]
                matched_rtp_key = tvg_name
                matched_rtp_names.add(tvg_name)
        
        # 创建新频道信息
        new_channel = channel.copy()
        
        if matched_rtp:
            new_channel['url'] = matched_rtp[0]
        
        if standard_name:
            new_channel['tvg-name'] = standard_name
            new_channel['group-title'] = mapper.find_group_title(standard_name)
            if not new_channel.get('channel-name'):
                new_channel['channel-name'] = standard_name
        else:
            if not new_channel.get('group-title'):
                new_channel['group-title'] = '其他'
            if not new_channel.get('channel-name'):
                new_channel['channel-name'] = new_channel.get('tvg-name', '')
        
        return new_channel
    
    def export_to_json(self, output_path: Optional[str] = None) -> str:
        """导出为JSON格式"""
        output_path = self._get_output_path(output_path, '.json')
        
        data = {
            'header': self.header_info,
            'channels': self.channels
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(output_path)
    
    def export_to_csv(self, output_path: Optional[str] = None) -> str:
        """导出为CSV格式"""
        output_path = self._get_output_path(output_path, '.csv')
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            if not self.channels:
                return str(output_path)
            
            fieldnames = ['tvg-name', 'tvg-logo', 'tvg-id', 'group-title', 'channel-name', 'url']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for channel in self.channels:
                writer.writerow(channel)
        
        return str(output_path)
    
    def generate_m3u(self, output_path: Optional[str] = None, 
                     url_mapping: Optional[Dict[str, str]] = None) -> str:
        """重新生成M3U文件"""
        output_path = self._get_output_path(output_path, '.generated.m3u')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            self._write_header(f)
            self._write_channels(f, url_mapping)
        
        return str(output_path)
    
    def _get_output_path(self, output_path: Optional[str], suffix: str) -> Path:
        """获取输出文件路径"""
        if output_path is None:
            return self.file_path.with_suffix(suffix)
        return Path(output_path)
    
    def _write_header(self, f):
        """写入M3U文件头"""
        if self.header_info.get('name'):
            f.write(f'#EXTM3U name="{self.header_info["name"]}"\n')
        if self.header_info.get('x-tvg-url'):
            f.write(f'#EXTM3U x-tvg-url="{self.header_info["x-tvg-url"]}"\n')
    
    def _write_channels(self, f, url_mapping: Optional[Dict[str, str]]):
        """写入频道信息"""
        for channel in self.channels:
            # 如果 tvg-logo 为空，尝试从两个 URL 获取 logo
            if not channel.get('tvg-logo'):
                logo_url = self._try_get_logo_url(channel.get('tvg-name', ''))
                if logo_url:
                    channel['tvg-logo'] = logo_url
            
            f.write(self._build_extinf_line(channel) + '\n')
            
            url = self._get_channel_url(channel, url_mapping)
            if url:
                f.write(url + '\n')
    
    def _build_extinf_line(self, channel: Dict) -> str:
        """构建 #EXTINF 行"""
        duration = channel.get('duration', '-1')
        extinf = f'#EXTINF:{duration}'
        
        attrs = []
        for key in ['tvg-id', 'tvg-name', 'tvg-logo', 'group-title']:
            if channel.get(key):
                attrs.append(f'{key}="{channel[key]}"')
        
        if attrs:
            extinf += ',' + ' '.join(attrs)
        
        channel_name = channel.get('channel-name', channel.get('tvg-name', ''))
        if channel_name:
            extinf += f',{channel_name}'
        
        return extinf
    
    def _get_channel_url(self, channel: Dict, url_mapping: Optional[Dict[str, str]]) -> str:
        """获取频道URL"""
        if url_mapping and channel.get('tvg-name') in url_mapping:
            return url_mapping[channel['tvg-name']]
        return channel.get('url', '')
    
    def _check_url_exists(self, url: str, timeout: int = 5) -> bool:
        """
        检查 URL 是否可以访问
        
        Args:
            url: 要检查的 URL
            timeout: 超时时间（秒）
            
        Returns:
            如果 URL 可以访问返回 True，否则返回 False
        """
        try:
            # 先尝试 HEAD 请求（更高效）
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                return True
        except:
            pass
        
        try:
            # 如果 HEAD 请求失败，尝试 GET 请求（只获取头部，不下载内容）
            response = requests.get(url, timeout=timeout, stream=True, allow_redirects=True)
            # 立即关闭连接，不下载内容
            response.close()
            return response.status_code == 200
        except:
            return False
    
    def _try_get_logo_url(self, tvg_name: str) -> Optional[str]:
        """
        尝试从两个 URL 获取 logo
        
        Args:
            tvg_name: 频道名称（tvg-name）
            
        Returns:
            如果找到可访问的 logo URL，返回 URL；否则返回 None
        """
        if not tvg_name:
            return None
        
        # 两个 logo URL 模板，先尝试原始名称（兼容现有格式如 CCTV5+）
        logo_urls = [
            f"https://epg.112114.xyz/logo/{tvg_name}.png",
            f"https://live.fanmingming.com/tv/{tvg_name}.png"
        ]
        
        # 尝试每个 URL
        for logo_url in logo_urls:
            if self._check_url_exists(logo_url):
                return logo_url
        
        # 如果原始名称失败，尝试 URL 编码的版本（处理特殊字符）
        encoded_name = quote(tvg_name, safe='')
        encoded_logo_urls = [
            f"https://epg.112114.xyz/logo/{encoded_name}.png",
            f"https://live.fanmingming.com/tv/{encoded_name}.png"
        ]
        
        for logo_url in encoded_logo_urls:
            if self._check_url_exists(logo_url):
                return logo_url
        
        return None
    
    def deduplicate_urls(self) -> Dict:
        """
        去除重复的URL，保留第一个出现的频道（优先保留有logo的）
        
        Returns:
            包含去重统计信息的字典
        """
        seen_urls = {}
        deduplicated_channels = []
        removed_count = 0
        removed_channels = []
        
        for channel in self.channels:
            url = channel.get('url', '')
            if not url:
                # 没有URL的频道直接保留
                deduplicated_channels.append(channel)
                continue
            
            if url not in seen_urls:
                # 第一次出现，直接添加
                seen_urls[url] = channel
                deduplicated_channels.append(channel)
            else:
                # 重复URL，优先保留有logo的频道
                existing = seen_urls[url]
                existing_has_logo = bool(existing.get('tvg-logo'))
                current_has_logo = bool(channel.get('tvg-logo'))
                
                if not existing_has_logo and current_has_logo:
                    # 替换为有logo的频道
                    idx = deduplicated_channels.index(existing)
                    removed_channels.append({
                        'name': existing.get('tvg-name', existing.get('channel-name', '未知')),
                        'url': url,
                        'reason': '被有logo的频道替换'
                    })
                    deduplicated_channels[idx] = channel
                    seen_urls[url] = channel
                    removed_count += 1
                else:
                    # 保留已存在的频道
                    removed_channels.append({
                        'name': channel.get('tvg-name', channel.get('channel-name', '未知')),
                        'url': url,
                        'reason': 'URL重复，保留第一个'
                    })
                    removed_count += 1
        
        original_count = len(self.channels)
        self.channels = deduplicated_channels
        
        return {
            'original_count': original_count,
            'deduplicated_count': len(deduplicated_channels),
            'removed_count': removed_count,
            'removed_channels': removed_channels
        }
    
    def get_summary(self) -> Dict:
        """获取解析摘要信息"""
        total_channels = len(self.channels)
        channels_with_name = sum(1 for c in self.channels if c.get('tvg-name'))
        channels_with_logo = sum(1 for c in self.channels if c.get('tvg-logo'))
        channels_with_url = sum(1 for c in self.channels if c.get('url'))
        
        group_titles = defaultdict(int)
        for channel in self.channels:
            group = channel.get('group-title', '未分类')
            group_titles[group] += 1
        
        return {
            'total_channels': total_channels,
            'channels_with_name': channels_with_name,
            'channels_with_logo': channels_with_logo,
            'channels_with_url': channels_with_url,
            'group_titles': dict(group_titles)
        }


class M3UComparator:
    """M3U文件比较器"""
    
    @staticmethod
    def compare(file1_path: str, file2_path: str, 
                output_file: Optional[str] = None,
                config_file: str = "source/zubo/data.py") -> Dict:
        """
        比较两个M3U文件的URL差异
        
        Args:
            file1_path: 第一个M3U文件路径
            file2_path: 第二个M3U文件路径
            output_file: 输出差异报告文件路径（可选）
            config_file: 配置文件路径
            
        Returns:
            包含差异信息的字典
        """
        playlist1 = M3UPlaylist(file1_path)
        playlist2 = M3UPlaylist(file2_path)
        
        channels1 = playlist1.parse()
        channels2 = playlist2.parse()
        
        # 加载配置
        try:
            _, channel_mapping, _ = ChannelConfigLoader.load(config_file)
            mapper = ChannelMapper(channel_mapping, {})
        except:
            mapper = ChannelMapper({}, {})
        
        # 构建频道映射
        channels1_map = M3UComparator._build_channel_map(channels1, mapper)
        channels2_map = M3UComparator._build_channel_map(channels2, mapper)
        
        # 比较差异
        result = M3UComparator._compare_maps(channels1_map, channels2_map, 
                                            file1_path, file2_path, 
                                            len(channels1), len(channels2))
        
        # 生成报告
        if output_file:
            M3UComparator._write_report(result, output_file)
        
        return result
    
    @staticmethod
    def _build_channel_map(channels: List[Dict], mapper: ChannelMapper) -> Dict:
        """构建频道名到频道信息的映射"""
        channel_map = {}
        for ch in channels:
            tvg_name = ch.get('tvg-name', '') or ch.get('channel-name', '')
            if tvg_name:
                standard_name = mapper.normalize_name(tvg_name)
                if standard_name not in channel_map:
                    channel_map[standard_name] = []
                channel_map[standard_name].append({
                    'url': ch.get('url', ''),
                    'tvg-name': ch.get('tvg-name', ''),
                    'channel-name': ch.get('channel-name', ''),
                    'group-title': ch.get('group-title', ''),
                    'tvg-logo': ch.get('tvg-logo', '')
                })
        return channel_map
    
    @staticmethod
    def _compare_maps(map1: Dict, map2: Dict, file1: str, file2: str,
                     count1: int, count2: int) -> Dict:
        """比较两个频道映射"""
        differences = []
        only_in_file1 = []
        only_in_file2 = []
        same_urls = []
        
        all_names = set(map1.keys()) | set(map2.keys())
        
        for name in sorted(all_names):
            ch1_list = map1.get(name, [])
            ch2_list = map2.get(name, [])
            
            if not ch1_list:
                for ch2 in ch2_list:
                    only_in_file2.append({
                        'name': name,
                        'url': ch2['url'],
                        'tvg-name': ch2['tvg-name'],
                        'group-title': ch2['group-title']
                    })
            elif not ch2_list:
                for ch1 in ch1_list:
                    only_in_file1.append({
                        'name': name,
                        'url': ch1['url'],
                        'tvg-name': ch1['tvg-name'],
                        'group-title': ch1['group-title']
                    })
            else:
                urls1 = {ch['url'] for ch in ch1_list}
                urls2 = {ch['url'] for ch in ch2_list}
                
                if urls1 == urls2:
                    same_urls.append({
                        'name': name,
                        'url': list(urls1)[0] if urls1 else '',
                        'tvg-name': ch1_list[0].get('tvg-name', ''),
                        'group-title': ch1_list[0].get('group-title', '')
                    })
                else:
                    differences.append({
                        'name': name,
                        'file1_urls': sorted(list(urls1)),
                        'file2_urls': sorted(list(urls2)),
                        'tvg-name': ch1_list[0].get('tvg-name', ''),
                        'group-title': ch1_list[0].get('group-title', '')
                    })
        
        return {
            'file1': file1,
            'file2': file2,
            'file1_total': count1,
            'file2_total': count2,
            'differences': differences,
            'only_in_file1': only_in_file1,
            'only_in_file2': only_in_file2,
            'same_urls': same_urls,
            'diff_count': len(differences),
            'only_file1_count': len(only_in_file1),
            'only_file2_count': len(only_in_file2),
            'same_count': len(same_urls)
        }
    
    @staticmethod
    def _write_report(result: Dict, output_file: str):
        """写入比较报告"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("M3U文件URL差异比较报告\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"文件1: {result['file1']}\n")
            f.write(f"文件2: {result['file2']}\n\n")
            f.write("统计信息:\n")
            f.write(f"  文件1总频道数: {result['file1_total']}\n")
            f.write(f"  文件2总频道数: {result['file2_total']}\n")
            f.write(f"  URL相同的频道: {result['same_count']}\n")
            f.write(f"  URL不同的频道: {result['diff_count']}\n")
            f.write(f"  仅在文件1中的频道: {result['only_file1_count']}\n")
            f.write(f"  仅在文件2中的频道: {result['only_file2_count']}\n\n")
            
            if result['differences']:
                f.write("=" * 60 + "\n")
                f.write(f"URL不同的频道 ({len(result['differences'])}个):\n")
                f.write("=" * 60 + "\n\n")
                for diff in result['differences']:
                    f.write(f"频道名称: {diff['name']}\n")
                    f.write(f"  分组: {diff.get('group-title', 'N/A')}\n")
                    f.write("  文件1 URL:\n")
                    for url in diff['file1_urls']:
                        f.write(f"    - {url}\n")
                    f.write("  文件2 URL:\n")
                    for url in diff['file2_urls']:
                        f.write(f"    - {url}\n")
                    f.write("\n")
            
            if result['only_in_file1']:
                f.write("=" * 60 + "\n")
                f.write(f"仅在文件1中的频道 ({len(result['only_in_file1'])}个):\n")
                f.write("=" * 60 + "\n\n")
                for ch in result['only_in_file1']:
                    f.write(f"频道名称: {ch['name']}\n")
                    f.write(f"  分组: {ch.get('group-title', 'N/A')}\n")
                    f.write(f"  URL: {ch['url']}\n\n")
            
            if result['only_in_file2']:
                f.write("=" * 60 + "\n")
                f.write(f"仅在文件2中的频道 ({len(result['only_in_file2'])}个):\n")
                f.write("=" * 60 + "\n\n")
                for ch in result['only_in_file2']:
                    f.write(f"频道名称: {ch['name']}\n")
                    f.write(f"  分组: {ch.get('group-title', 'N/A')}\n")
                    f.write(f"  URL: {ch['url']}\n\n")


def batch_process_rtp(template_file: str, rtp_dir: str, output_dir: str,
                      config_file: str = "source/zubo/data.py") -> Dict:
    """
    批量处理RTP文件，使用模板M3U文件合并所有RTP文件
    
    Args:
        template_file: 模板M3U文件路径
        rtp_dir: RTP文件目录
        output_dir: 输出目录
        config_file: 配置文件路径
        
    Returns:
        处理结果字典，包含每个文件的处理信息和缺少logo的频道列表
    """
    template_path = Path(template_file)
    rtp_dir_path = Path(rtp_dir)
    output_dir_path = Path(output_dir)
    
    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")
    if not rtp_dir_path.exists():
        raise FileNotFoundError(f"RTP目录不存在: {rtp_dir_path}")
    
    # 创建输出目录
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    # 获取所有RTP文件
    rtp_files = list(rtp_dir_path.glob("*.txt"))
    
    results = {
        'processed': [],
        'failed': [],
        'no_logo_channels': {}
    }
    
    print(f"📋 找到 {len(rtp_files)} 个RTP文件")
    print(f"📁 输出目录: {output_dir_path}\n")
    
    for rtp_file in sorted(rtp_files):
        try:
            print(f"🔄 正在处理: {rtp_file.name}")
            
            # 加载模板
            playlist = M3UPlaylist(template_file)
            playlist.parse()
            
            # 合并RTP文件（只保留RTP中存在的频道）
            channels = playlist.merge_with_rtp(
                rtp_file.name,
                rtp_dir=str(rtp_dir_path),
                config_file=config_file,
                filter_only=True
            )
            
            # 检查缺少logo的频道
            no_logo_channels = [
                ch.get('tvg-name', ch.get('channel-name', '未知'))
                for ch in channels
                if not ch.get('tvg-logo')
            ]
            
            if no_logo_channels:
                results['no_logo_channels'][rtp_file.stem] = no_logo_channels
            
            # 生成输出文件名
            output_file = output_dir_path / f"{rtp_file.stem}.m3u"
            
            # 导出M3U文件
            playlist.generate_m3u(str(output_file))
            
            results['processed'].append({
                'rtp_file': rtp_file.name,
                'output_file': str(output_file),
                'channel_count': len(channels),
                'no_logo_count': len(no_logo_channels)
            })
            
            print(f"  ✅ 完成: {len(channels)} 个频道，{len(no_logo_channels)} 个缺少logo")
            
        except Exception as e:
            error_msg = f"处理 {rtp_file.name} 失败: {e}"
            results['failed'].append({
                'rtp_file': rtp_file.name,
                'error': str(e)
            })
            print(f"  ❌ {error_msg}")
    
    return results


def batch_process_m3u(input_dir: str, output_dir: str, 
                     dedup: bool = False) -> Dict:
    """
    批量处理M3U文件，从输入目录读取所有m3u文件，处理后输出到输出目录
    
    Args:
        input_dir: 输入M3U文件目录
        output_dir: 输出目录
        dedup: 是否去除重复的URL
        
    Returns:
        处理结果字典，包含每个文件的处理信息
    """
    input_dir_path = Path(input_dir)
    output_dir_path = Path(output_dir)
    
    if not input_dir_path.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_dir_path}")
    
    # 创建输出目录
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    # 获取所有M3U文件
    m3u_files = list(input_dir_path.glob("*.m3u"))
    
    results = {
        'processed': [],
        'failed': [],
        'total_channels': 0,
        'channels_with_logo_added': 0
    }
    
    print(f"📋 找到 {len(m3u_files)} 个M3U文件")
    print(f"📁 输入目录: {input_dir_path}")
    print(f"📁 输出目录: {output_dir_path}\n")
    
    for m3u_file in sorted(m3u_files):
        try:
            print(f"🔄 正在处理: {m3u_file.name}")
            
            # 加载并解析M3U文件
            playlist = M3UPlaylist(str(m3u_file))
            channels = playlist.parse()
            
            # 统计补充logo的频道数
            channels_with_logo_added = 0
            
            # 如果去重，执行去重操作
            if dedup:
                dedup_result = playlist.deduplicate_urls()
                channels = playlist.channels
                print(f"  📊 去重: {dedup_result['original_count']} -> {dedup_result['deduplicated_count']} 个频道")
            
            # 检查并补充logo（在generate_m3u时会自动处理）
            # 但我们需要先统计一下有多少频道缺少logo
            no_logo_before = sum(1 for ch in channels if not ch.get('tvg-logo'))
            
            # 生成输出文件名
            output_file = output_dir_path / m3u_file.name
            
            # 导出M3U文件（会自动补充logo）
            playlist.generate_m3u(str(output_file))
            
            # 重新加载输出文件以统计补充的logo
            output_playlist = M3UPlaylist(str(output_file))
            output_channels = output_playlist.parse()
            no_logo_after = sum(1 for ch in output_channels if not ch.get('tvg-logo'))
            channels_with_logo_added = no_logo_before - no_logo_after
            
            results['processed'].append({
                'input_file': m3u_file.name,
                'output_file': str(output_file),
                'channel_count': len(channels),
                'logo_added': channels_with_logo_added
            })
            
            results['total_channels'] += len(channels)
            results['channels_with_logo_added'] += channels_with_logo_added
            
            print(f"  ✅ 完成: {len(channels)} 个频道，补充了 {channels_with_logo_added} 个logo")
            
        except Exception as e:
            error_msg = f"处理 {m3u_file.name} 失败: {e}"
            results['failed'].append({
                'input_file': m3u_file.name,
                'error': str(e)
            })
            print(f"  ❌ {error_msg}")
            import traceback
            traceback.print_exc()
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='M3U播放列表处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 解析M3U文件并导出JSON
  %(prog)s input.m3u -f json

  # 合并RTP文件并生成新的M3U
  %(prog)s input.m3u --rtp 湖北电信.txt -f m3u -o output.m3u

  # 批量处理所有RTP文件
  %(prog)s template.m3u --batch --rtp-dir source/zubo/rtp --output-dir m3u

  # 批量处理M3U文件（从目录读取并输出到另一个目录）
  %(prog)s --batch-m3u --input-dir m3u --output-dir m3u_processed

  # 比较两个M3U文件的URL差异
  %(prog)s file1.m3u --compare file2.m3u --compare-output report.txt
        """
    )
    
    parser.add_argument('input_file', nargs='?', help='输入的M3U文件路径（批量处理时作为模板）')
    parser.add_argument('-o', '--output', help='输出文件路径（可选）')
    parser.add_argument('-f', '--format', choices=['json', 'csv', 'm3u'], 
                       default='json', help='输出格式（默认：json）')
    parser.add_argument('-s', '--summary', action='store_true', 
                       help='显示解析摘要信息')
    parser.add_argument('--rtp', help='RTP文件路径（相对于rtp目录，如：上海市电信.txt）')
    parser.add_argument('--rtp-dir', default='source/zubo/rtp', 
                       help='RTP文件目录（默认：source/zubo/rtp）')
    parser.add_argument('--config', default='source/zubo/data.py',
                       help='配置文件路径（默认：source/zubo/data.py）')
    parser.add_argument('--compare', help='要比较的第二个M3U文件路径')
    parser.add_argument('--compare-output', help='比较结果输出文件路径（可选）')
    parser.add_argument('--batch', action='store_true',
                       help='批量处理模式：处理rtp-dir中所有txt文件')
    parser.add_argument('--output-dir', default='m3u',
                       help='批量处理时的输出目录（默认：m3u）')
    parser.add_argument('--report', help='批量处理时输出缺少logo的频道报告文件路径')
    parser.add_argument('--dedup', action='store_true',
                       help='去除重复的URL（保留第一个出现的，优先保留有logo的）')
    parser.add_argument('--batch-m3u', action='store_true',
                       help='批量处理M3U文件模式：从input-dir读取所有m3u文件，处理后输出到output-dir')
    parser.add_argument('--input-dir', help='批量处理M3U时的输入目录')
    
    args = parser.parse_args()
    
    # 批量处理M3U文件模式
    if args.batch_m3u:
        if not args.input_dir:
            parser.error("批量处理M3U模式需要指定 --input-dir 参数")
        
        try:
            results = batch_process_m3u(
                args.input_dir,
                args.output_dir,
                dedup=args.dedup
            )
            
            print(f"\n📊 批量处理完成:")
            print(f"  ✅ 成功: {len(results['processed'])} 个文件")
            print(f"  ❌ 失败: {len(results['failed'])} 个文件")
            print(f"  📺 总频道数: {results['total_channels']}")
            print(f"  🖼️  补充logo数: {results['channels_with_logo_added']}")
            
            if results['failed']:
                print(f"\n❌ 失败的文件:")
                for item in results['failed']:
                    print(f"  - {item['input_file']}: {item['error']}")
            
            return
        
        except Exception as e:
            print(f"❌ 批量处理失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 批量处理RTP模式
    if args.batch:
        if not args.input_file:
            parser.error("批量处理模式需要指定模板M3U文件")
        
        try:
            results = batch_process_rtp(
                args.input_file,
                args.rtp_dir,
                args.output_dir,
                args.config
            )
            
            print(f"\n📊 批量处理完成:")
            print(f"  ✅ 成功: {len(results['processed'])} 个文件")
            print(f"  ❌ 失败: {len(results['failed'])} 个文件")
            
            if results['failed']:
                print(f"\n❌ 失败的文件:")
                for item in results['failed']:
                    print(f"  - {item['rtp_file']}: {item['error']}")
            
            # 生成缺少logo的频道报告
            if results['no_logo_channels']:
                report_content = "缺少tvg-logo的频道报告\n"
                report_content += "=" * 60 + "\n\n"
                
                for rtp_name, channels in sorted(results['no_logo_channels'].items()):
                    report_content += f"{rtp_name} ({len(channels)}个):\n"
                    for ch in channels:
                        report_content += f"  - {ch}\n"
                    report_content += "\n"
                
                if args.report:
                    report_path = Path(args.report)
                else:
                    report_path = Path(args.output_dir) / "no_logo_report.txt"
                
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                print(f"\n📝 缺少logo的频道报告已保存到: {report_path}")
                print(f"   共 {len(results['no_logo_channels'])} 个文件有缺少logo的频道")
            else:
                print(f"\n✅ 所有频道都有logo")
            
            return
        
        except Exception as e:
            print(f"❌ 批量处理失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    if not args.input_file:
        parser.error("需要指定input_file参数")
    
    # 如果指定了比较文件，执行比较
    if args.compare:
        print(f"🔍 正在比较两个M3U文件...")
        print(f"  文件1: {args.input_file}")
        print(f"  文件2: {args.compare}")
        
        try:
            result = M3UComparator.compare(
                args.input_file,
                args.compare,
                output_file=args.compare_output,
                config_file=args.config
            )
            
            print(f"\n📊 比较结果:")
            print(f"  文件1总频道数: {result['file1_total']}")
            print(f"  文件2总频道数: {result['file2_total']}")
            print(f"  ✅ URL相同的频道: {result['same_count']}")
            print(f"  ⚠️  URL不同的频道: {result['diff_count']}")
            print(f"  📄 仅在文件1中的频道: {result['only_file1_count']}")
            print(f"  📄 仅在文件2中的频道: {result['only_file2_count']}")
            
            if result['differences']:
                print(f"\n🔴 URL不同的频道列表 (前10个):")
                for i, diff in enumerate(result['differences'][:10], 1):
                    print(f"  {i}. {diff['name']}")
                    print(f"     文件1: {diff['file1_urls'][0]}")
                    print(f"     文件2: {diff['file2_urls'][0]}")
                if len(result['differences']) > 10:
                    print(f"     ... 还有 {len(result['differences']) - 10} 个差异")
            
            if args.compare_output:
                print(f"\n💾 详细报告已保存到: {args.compare_output}")
            else:
                print(f"\n💡 提示: 使用 --compare-output 参数可保存详细报告")
            
            return
        
        except Exception as e:
            print(f"❌ 比较失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 如果指定了比较文件，执行比较
    if args.compare:
        print(f"🔍 正在比较两个M3U文件...")
        print(f"  文件1: {args.input_file}")
        print(f"  文件2: {args.compare}")
        
        try:
            result = M3UComparator.compare(
                args.input_file,
                args.compare,
                output_file=args.compare_output,
                config_file=args.config
            )
            
            print(f"\n📊 比较结果:")
            print(f"  文件1总频道数: {result['file1_total']}")
            print(f"  文件2总频道数: {result['file2_total']}")
            print(f"  ✅ URL相同的频道: {result['same_count']}")
            print(f"  ⚠️  URL不同的频道: {result['diff_count']}")
            print(f"  📄 仅在文件1中的频道: {result['only_file1_count']}")
            print(f"  📄 仅在文件2中的频道: {result['only_file2_count']}")
            
            if result['differences']:
                print(f"\n🔴 URL不同的频道列表 (前10个):")
                for i, diff in enumerate(result['differences'][:10], 1):
                    print(f"  {i}. {diff['name']}")
                    print(f"     文件1: {diff['file1_urls'][0]}")
                    print(f"     文件2: {diff['file2_urls'][0]}")
                if len(result['differences']) > 10:
                    print(f"     ... 还有 {len(result['differences']) - 10} 个差异")
            
            if args.compare_output:
                print(f"\n💾 详细报告已保存到: {args.compare_output}")
            else:
                print(f"\n💡 提示: 使用 --compare-output 参数可保存详细报告")
            
            return
        
        except Exception as e:
            print(f"❌ 比较失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 解析M3U文件
    playlist = M3UPlaylist(args.input_file)
    channels = playlist.parse()
    
    print(f"✅ 成功解析 {len(channels)} 个频道")
    
    # 如果指定了去重，执行去重
    if args.dedup:
        print(f"\n🔄 正在去除重复的URL...")
        try:
            dedup_result = playlist.deduplicate_urls()
            print(f"✅ 去重完成:")
            print(f"  原始频道数: {dedup_result['original_count']}")
            print(f"  去重后频道数: {dedup_result['deduplicated_count']}")
            print(f"  移除重复频道数: {dedup_result['removed_count']}")
            
            if dedup_result['removed_channels']:
                print(f"\n📋 移除的频道列表 (前10个):")
                for i, ch in enumerate(dedup_result['removed_channels'][:10], 1):
                    print(f"  {i}. {ch['name']} - {ch['reason']}")
                    print(f"     URL: {ch['url']}")
                if len(dedup_result['removed_channels']) > 10:
                    print(f"     ... 还有 {len(dedup_result['removed_channels']) - 10} 个被移除的频道")
            
            channels = playlist.channels
        except Exception as e:
            print(f"❌ 去重失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 如果指定了RTP文件，进行合并
    if args.rtp:
        print(f"\n🔄 正在合并RTP文件: {args.rtp}")
        try:
            channels = playlist.merge_with_rtp(
                args.rtp,
                rtp_dir=args.rtp_dir,
                config_file=args.config
            )
            print(f"✅ 合并完成，共 {len(channels)} 个频道（包含新增的RTP频道）")
        except Exception as e:
            print(f"❌ 合并失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 显示摘要
    if args.summary:
        summary = playlist.get_summary()
        print("\n📊 解析摘要:")
        print(f"  总频道数: {summary['total_channels']}")
        print(f"  有tvg-name的频道: {summary['channels_with_name']}")
        print(f"  有tvg-logo的频道: {summary['channels_with_logo']}")
        print(f"  有URL的频道: {summary['channels_with_url']}")
        print(f"\n📁 分组统计:")
        for group, count in sorted(summary['group_titles'].items()):
            print(f"  {group}: {count}")
    
    # 导出文件
    if args.format == 'json':
        output_path = playlist.export_to_json(args.output)
        print(f"\n💾 已导出JSON文件: {output_path}")
    elif args.format == 'csv':
        output_path = playlist.export_to_csv(args.output)
        print(f"\n💾 已导出CSV文件: {output_path}")
    elif args.format == 'm3u':
        output_path = playlist.generate_m3u(args.output)
        print(f"\n💾 已生成M3U文件: {output_path}")
    
    # 显示前几个频道示例
    if channels:
        print(f"\n📺 前3个频道示例:")
        for i, channel in enumerate(channels[:3], 1):
            print(f"  {i}. {channel.get('tvg-name', 'N/A')} (ID: {channel.get('tvg-id', 'N/A')})")
            print(f"     Logo: {channel.get('tvg-logo', 'N/A')}")
            print(f"     分组: {channel.get('group-title', 'N/A')}")
            url = channel.get('url', 'N/A')
            if len(url) > 60:
                url = url[:60] + '...'
            print(f"     URL: {url}")


if __name__ == '__main__':
    main()
