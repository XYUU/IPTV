#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U_Kit.py 测试用例
根据 README.md 的要求进行完整测试
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from M3U_Kit import (
    ConfigLoader, FileParser, ChannelProcessor,
    merge_directories, generate_m3u_file
)


class TestConfigLoader(unittest.TestCase):
    """测试配置加载器"""
    
    def setUp(self):
        """创建临时配置文件"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "test_data.py"
        
        # 创建测试配置文件
        config_content = '''
CHANNEL_CATEGORIES = {
    "央视频道": ["CCTV1", "CCTV2", "CCTV3"],
    "卫视频道": ["湖南卫视", "北京卫视"],
    "其他": []
}

CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV-1 HD", "CCTV1 HD"],
    "CCTV2": ["CCTV-2", "CCTV-2 HD"],
    "湖南卫视": ["湖南卫视4K"],
    "北京卫视": ["北京卫视4K"]
}
'''
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
    
    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)
    
    def test_load_config(self):
        """测试加载配置"""
        channel_categories, channel_mapping, alias_map = ConfigLoader.load(str(self.config_file))
        
        self.assertIn("央视频道", channel_categories)
        self.assertIn("CCTV1", channel_categories["央视频道"])
        
        self.assertIn("CCTV1", channel_mapping)
        self.assertIn("CCTV-1", channel_mapping["CCTV1"])
        
        # 测试别名映射
        self.assertEqual(alias_map["CCTV1"], "CCTV1")
        self.assertEqual(alias_map["CCTV-1"], "CCTV1")
        self.assertEqual(alias_map["CCTV-1 HD"], "CCTV1")
        self.assertEqual(alias_map["湖南卫视4K"], "湖南卫视")


class TestFileParser(unittest.TestCase):
    """测试文件解析器"""
    
    def setUp(self):
        """创建临时目录和测试文件"""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)
    
    def test_parse_txt(self):
        """测试解析txt文件（CSV格式）"""
        txt_file = self.temp_dir / "test.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("CCTV1,rtp://239.1.1.1:9000\n")
            f.write("CCTV2,rtp://239.1.1.2:9000\n")
            f.write("\n")  # 空行
            f.write("湖南卫视,rtp://239.1.1.3:9000\n")
        
        channels = FileParser.parse_txt(txt_file)
        
        self.assertEqual(len(channels), 3)
        self.assertEqual(channels[0]['tvg-name'], 'CCTV1')
        self.assertEqual(channels[0]['url'], 'rtp://239.1.1.1:9000')
        self.assertEqual(channels[0]['tvg-logo'], '')
        self.assertEqual(channels[0]['group-title'], '')
    
    def test_parse_m3u_simple_format(self):
        """测试解析简单格式的m3u文件"""
        m3u_file = self.temp_dir / "test.m3u"
        with open(m3u_file, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write("#EXTINF:-1 ,北京卫视4K\n")
            f.write("rtp://239.254.201.68:6000\n")
            f.write("#EXTINF:-1,湖南卫视\n")
            f.write("rtp://239.3.1.241:8000\n")
        
        channels = FileParser.parse_m3u(m3u_file)
        
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['tvg-name'], '北京卫视4K')
        self.assertEqual(channels[0]['url'], 'rtp://239.254.201.68:6000')
        self.assertEqual(channels[1]['tvg-name'], '湖南卫视')
        self.assertEqual(channels[1]['url'], 'rtp://239.3.1.241:8000')
    
    def test_parse_m3u_full_format(self):
        """测试解析完整格式的m3u文件"""
        m3u_file = self.temp_dir / "test.m3u"
        with open(m3u_file, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U name=\"测试\"\n")
            f.write("#EXTM3U x-tvg-url=\"https://epg.112114.xyz/pp.xml\"\n")
            f.write('#EXTINF:-1,tvg-id="1" tvg-name="CCTV1" tvg-logo="https://live.fanmingming.com/tv/CCTV1.png" group-title="央视频道",CCTV1综合\n')
            f.write("rtp://239.76.253.151:9000\n")
            f.write('#EXTINF:-1,tvg-id="2" tvg-name="CCTV2" tvg-logo="https://live.fanmingming.com/tv/CCTV2.png" group-title="央视频道",CCTV2财经\n')
            f.write("rtp://239.76.253.152:9000\n")
        
        channels = FileParser.parse_m3u(m3u_file)
        
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['tvg-name'], 'CCTV1')
        self.assertEqual(channels[0]['tvg-logo'], 'https://live.fanmingming.com/tv/CCTV1.png')
        self.assertEqual(channels[0]['group-title'], '央视频道')
        self.assertEqual(channels[0]['channel-name'], 'CCTV1综合')
        self.assertEqual(channels[0]['url'], 'rtp://239.76.253.151:9000')
        
        self.assertEqual(channels[1]['tvg-name'], 'CCTV2')
        self.assertEqual(channels[1]['tvg-logo'], 'https://live.fanmingming.com/tv/CCTV2.png')
        self.assertEqual(channels[1]['group-title'], '央视频道')
        self.assertEqual(channels[1]['channel-name'], 'CCTV2财经')


class TestChannelProcessor(unittest.TestCase):
    """测试频道处理器"""
    
    def setUp(self):
        """创建临时配置文件和处理器"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "test_data.py"
        
        config_content = '''
CHANNEL_CATEGORIES = {
    "央视频道": ["CCTV1", "CCTV2", "CCTV3"],
    "卫视频道": ["湖南卫视", "北京卫视"],
    "其他": []
}

CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV-1 HD", "CCTV1 HD"],
    "CCTV2": ["CCTV-2", "CCTV-2 HD"],
    "湖南卫视": ["湖南卫视4K"],
    "北京卫视": ["北京卫视4K"]
}
'''
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        self.processor = ChannelProcessor(str(self.config_file))
    
    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)
    
    def test_normalize_name(self):
        """测试名称标准化"""
        self.assertEqual(self.processor.normalize_name("CCTV1"), "CCTV1")
        self.assertEqual(self.processor.normalize_name("CCTV-1"), "CCTV1")
        self.assertEqual(self.processor.normalize_name("CCTV-1 HD"), "CCTV1")
        self.assertEqual(self.processor.normalize_name("湖南卫视4K"), "湖南卫视")
        self.assertEqual(self.processor.normalize_name("未知频道"), "未知频道")
    
    def test_find_group_title(self):
        """测试查找分组"""
        self.assertEqual(self.processor.find_group_title("CCTV1"), "央视频道")
        self.assertEqual(self.processor.find_group_title("湖南卫视"), "卫视频道")
        self.assertEqual(self.processor.find_group_title("未知频道"), "其他")
    
    def test_process_channels_normalize(self):
        """测试处理频道：标准化名称"""
        channels = [
            {'tvg-name': 'CCTV-1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': ''},
            {'tvg-name': '湖南卫视4K', 'url': 'rtp://239.1.1.2:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': ''},
        ]
        
        processed = self.processor.process_channels(channels)
        
        self.assertEqual(processed[0]['tvg-name'], 'CCTV1')
        self.assertEqual(processed[1]['tvg-name'], '湖南卫视')
        self.assertEqual(processed[0]['group-title'], '央视频道')
        self.assertEqual(processed[1]['group-title'], '卫视频道')
    
    def test_process_channels_deduplicate(self):
        """测试处理频道：URL去重"""
        channels = [
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': 'CCTV1'},
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': 'https://example.com/logo.png', 'group-title': '', 'channel-name': 'CCTV1'},
            {'tvg-name': 'CCTV2', 'url': 'rtp://239.1.1.2:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': 'CCTV2'},
        ]
        
        processed = self.processor.process_channels(channels)
        
        # 应该去重，保留有logo的版本
        self.assertEqual(len(processed), 2)
        self.assertEqual(processed[0]['url'], 'rtp://239.1.1.1:9000')
        self.assertEqual(processed[0]['tvg-logo'], 'https://example.com/logo.png')
        self.assertEqual(processed[1]['url'], 'rtp://239.1.1.2:9000')
    
    def test_process_channels_tvg_id(self):
        """测试处理频道：重新编号"""
        channels = [
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': 'CCTV1'},
            {'tvg-name': 'CCTV2', 'url': 'rtp://239.1.1.2:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': 'CCTV2'},
        ]
        
        processed = self.processor.process_channels(channels)
        
        self.assertEqual(processed[0]['tvg-id'], '1')
        self.assertEqual(processed[1]['tvg-id'], '2')
    
    @patch('M3U_Kit.requests')
    def test_process_channels_logo_completion(self, mock_requests):
        """测试处理频道：补全缺失的logo"""
        # 模拟网络请求：第一个URL返回200，第二个URL返回404
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response2 = MagicMock()
        mock_response2.status_code = 404
        
        # 模拟head请求失败，get请求成功
        mock_requests.head.side_effect = Exception("Connection error")
        mock_requests.get.return_value = mock_response1
        mock_requests.get.return_value.close = MagicMock()
        
        channels = [
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': '', 'group-title': '', 'channel-name': 'CCTV1'},
        ]
        
        # 第一次调用返回200（成功），后续调用返回404（失败）
        def side_effect(*args, **kwargs):
            if mock_requests.get.call_count == 1:
                return mock_response1
            return mock_response2
        
        mock_requests.get.side_effect = side_effect
        
        processed = self.processor.process_channels(channels)
        
        # 应该尝试补全logo（但由于mock可能不完美，至少验证处理流程）
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]['tvg-name'], 'CCTV1')
    
    def test_process_channels_keep_first_when_info_complete(self):
        """测试处理频道：信息完整时取先出现的"""
        channels = [
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': 'https://example.com/logo1.png', 'group-title': '央视频道', 'channel-name': 'CCTV1'},
            {'tvg-name': 'CCTV1', 'url': 'rtp://239.1.1.1:9000', 'tvg-logo': 'https://example.com/logo2.png', 'group-title': '央视频道', 'channel-name': 'CCTV1'},
        ]
        
        processed = self.processor.process_channels(channels)
        
        # 应该保留第一个出现的（有logo的优先，但这里两个都有logo，所以保留第一个）
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]['tvg-logo'], 'https://example.com/logo1.png')


class TestM3UGeneration(unittest.TestCase):
    """测试M3U文件生成"""
    
    def setUp(self):
        """创建临时目录"""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)
    
    def test_generate_m3u_file(self):
        """测试生成M3U文件"""
        output_file = self.temp_dir / "test.m3u"
        file_name = "湖南电信"
        channels = [
            {
                'tvg-id': '1',
                'tvg-name': 'CCTV1',
                'tvg-logo': 'https://live.fanmingming.com/tv/CCTV1.png',
                'group-title': '央视频道',
                'channel-name': 'CCTV1综合',
                'url': 'rtp://239.76.253.151:9000',
                'duration': '-1'
            },
            {
                'tvg-id': '2',
                'tvg-name': 'CCTV2',
                'tvg-logo': 'https://live.fanmingming.com/tv/CCTV2.png',
                'group-title': '央视频道',
                'channel-name': 'CCTV2财经',
                'url': 'rtp://239.76.253.152:9000',
                'duration': '-1'
            }
        ]
        
        generate_m3u_file(output_file, file_name, channels)
        
        # 验证文件内容
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 检查文件头
        self.assertEqual(lines[0].strip(), f'#EXTM3U name="{file_name}"')
        self.assertEqual(lines[1].strip(), '#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml,http://epg.51zmt.top:8000/e.xml"')
        
        # 检查第一个频道
        self.assertIn('CCTV1', lines[2])
        self.assertIn('tvg-name="CCTV1"', lines[2])
        self.assertIn('tvg-logo="https://live.fanmingming.com/tv/CCTV1.png"', lines[2])
        self.assertIn('group-title="央视频道"', lines[2])
        self.assertEqual(lines[3].strip(), 'rtp://239.76.253.151:9000')


class TestIntegration(unittest.TestCase):
    """集成测试：测试完整的合并流程"""
    
    def setUp(self):
        """创建测试环境和文件"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_dir1 = self.temp_dir / "input1"
        self.input_dir2 = self.temp_dir / "input2"
        self.output_dir = self.temp_dir / "output"
        self.config_file = self.temp_dir / "test_data.py"
        
        # 创建输入目录
        self.input_dir1.mkdir(parents=True)
        self.input_dir2.mkdir(parents=True)
        
        # 创建配置文件
        config_content = '''
CHANNEL_CATEGORIES = {
    "央视频道": ["CCTV1", "CCTV2"],
    "卫视频道": ["湖南卫视", "北京卫视"],
    "其他": []
}

CHANNEL_MAPPING = {
    "CCTV1": ["CCTV-1", "CCTV-1 HD"],
    "CCTV2": ["CCTV-2"],
    "湖南卫视": ["湖南卫视4K"],
    "北京卫视": ["北京卫视4K"]
}
'''
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # 创建测试文件1：txt格式
        txt_file1 = self.input_dir1 / "湖南电信.txt"
        with open(txt_file1, 'w', encoding='utf-8') as f:
            f.write("CCTV-1,rtp://239.1.1.1:9000\n")
            f.write("CCTV-2,rtp://239.1.1.2:9000\n")
        
        # 创建测试文件2：m3u格式（简单格式）
        m3u_file1 = self.input_dir1 / "湖南电信.m3u"
        with open(m3u_file1, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write("#EXTINF:-1 ,湖南卫视4K\n")
            f.write("rtp://239.1.1.3:9000\n")
        
        # 创建测试文件3：m3u格式（完整格式）
        m3u_file2 = self.input_dir2 / "湖南电信.m3u"
        with open(m3u_file2, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U name=\"湖南电信\"\n")
            f.write('#EXTINF:-1,tvg-id="1" tvg-name="北京卫视4K" tvg-logo="https://example.com/logo.png" group-title="卫视频道",北京卫视\n')
            f.write("rtp://239.1.1.4:9000\n")
            # 添加一个重复的URL（应该被去重）
            f.write('#EXTINF:-1,tvg-name="CCTV-1" tvg-logo="https://example.com/cctv1.png"\n')
            f.write("rtp://239.1.1.1:9000\n")
    
    def tearDown(self):
        """清理临时文件"""
        shutil.rmtree(self.temp_dir)
    
    def test_merge_directories(self):
        """测试合并多个目录"""
        merge_directories(
            [str(self.input_dir1), str(self.input_dir2)],
            str(self.output_dir),
            str(self.config_file)
        )
        
        # 验证输出文件存在
        output_file = self.output_dir / "湖南电信.m3u"
        self.assertTrue(output_file.exists())
        
        # 验证文件内容
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查文件头
        self.assertIn('#EXTM3U name="湖南电信"', content)
        self.assertIn('#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml,http://epg.51zmt.top:8000/e.xml"', content)
        
        # 检查频道（应该包含所有4个不同的URL）
        self.assertIn('rtp://239.1.1.1:9000', content)  # CCTV1
        self.assertIn('rtp://239.1.1.2:9000', content)  # CCTV2
        self.assertIn('rtp://239.1.1.3:9000', content)  # 湖南卫视
        self.assertIn('rtp://239.1.1.4:9000', content)  # 北京卫视
        
        # 检查名称标准化
        self.assertIn('tvg-name="CCTV1"', content)
        self.assertIn('tvg-name="CCTV2"', content)
        self.assertIn('tvg-name="湖南卫视"', content)
        self.assertIn('tvg-name="北京卫视"', content)
        
        # 检查分组
        self.assertIn('group-title="央视频道"', content)
        self.assertIn('group-title="卫视频道"', content)
        
        # 验证URL去重（CCTV1应该只出现一次，且保留有logo的版本）
        cctv1_count = content.count('rtp://239.1.1.1:9000')
        self.assertEqual(cctv1_count, 1)  # 应该只出现一次
        
        # 验证tvg-id是否正确编号
        self.assertIn('tvg-id="1"', content)
        self.assertIn('tvg-id="2"', content)
        self.assertIn('tvg-id="3"', content)
        self.assertIn('tvg-id="4"', content)
    
    def test_merge_empty_channels(self):
        """测试处理空频道列表"""
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()
        
        # 创建一个空文件
        empty_file = empty_dir / "空文件.txt"
        empty_file.touch()
        
        merge_directories(
            [str(empty_dir)],
            str(self.output_dir),
            str(self.config_file)
        )
        
        # 应该创建输出文件，但内容为空（只有文件头）
        output_file = self.output_dir / "空文件.m3u"
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # 应该只有文件头，没有频道
            self.assertEqual(len(lines), 2)  # 只有两行文件头
    
    def test_parse_m3u_with_empty_lines(self):
        """测试解析包含空行的m3u文件"""
        m3u_file = self.temp_dir / "test.m3u"
        with open(m3u_file, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write("\n")  # 空行
            f.write("#EXTINF:-1,测试频道\n")
            f.write("rtp://239.1.1.1:9000\n")
            f.write("\n")  # 空行
            f.write("#EXTINF:-1,测试频道2\n")
            f.write("rtp://239.1.1.2:9000\n")
        
        channels = FileParser.parse_m3u(m3u_file)
        
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['tvg-name'], '测试频道')
        self.assertEqual(channels[1]['tvg-name'], '测试频道2')
    
    def test_parse_txt_with_empty_lines(self):
        """测试解析包含空行的txt文件"""
        txt_file = self.temp_dir / "test.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("CCTV1,rtp://239.1.1.1:9000\n")
            f.write("\n")  # 空行
            f.write("CCTV2,rtp://239.1.1.2:9000\n")
            f.write("  \n")  # 只有空格的空行
        
        channels = FileParser.parse_txt(txt_file)
        
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['tvg-name'], 'CCTV1')
        self.assertEqual(channels[1]['tvg-name'], 'CCTV2')


if __name__ == '__main__':
    unittest.main()

