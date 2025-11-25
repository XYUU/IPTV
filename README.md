# M3U播放列表处理工具 - 用户手册

## 简介

M3U播放列表处理工具是一个功能强大的Python工具，用于解析、合并、比较和导出M3U播放列表文件。支持与RTP文件合并、频道映射、URL比较等功能。

## 功能特性

- ✅ **M3U文件解析**：解析M3U文件，提取频道信息（tvg-name、tvg-logo、group-title等）
- ✅ **RTP文件合并**：使用RTP文件替换M3U中的URL，支持频道名映射
- ✅ **URL比较**：比较两个M3U文件的URL差异
- ✅ **多格式导出**：支持导出为JSON、CSV、M3U格式
- ✅ **频道映射**：支持通过配置文件进行频道名标准化和分组
- ✅ **自动补充Logo**：自动从在线源获取缺失的频道Logo
- ✅ **批量处理**：支持批量处理目录中的所有M3U文件
- ✅ **URL去重**：自动去除重复的URL，优先保留有Logo的频道

## 安装要求

- Python 3.6+
- 依赖库：
  ```bash
  pip install requests
  ```

## 基本用法

### 1. 解析M3U文件

```bash
# 解析并导出为JSON（默认）
python zubo/M3U_Kit.py input.m3u

# 指定输出文件
python zubo/M3U_Kit.py input.m3u -o output.json

# 显示统计摘要
python zubo/M3U_Kit.py input.m3u -s
```

### 2. 导出为不同格式

```bash
# 导出为JSON格式
python zubo/M3U_Kit.py input.m3u -f json -o output.json

# 导出为CSV格式
python zubo/M3U_Kit.py input.m3u -f csv -o output.csv

# 导出为M3U格式（会自动补充缺失的Logo）
python zubo/M3U_Kit.py input.m3u -f m3u -o output.m3u
```

### 3. 合并RTP文件

```bash
# 基本用法：合并RTP文件并生成新的M3U
python zubo/m3u_parser.py input.m3u --rtp 湖北电信.txt -f m3u -o output.m3u

# 使用自定义RTP目录
python zubo/m3u_parser.py input.m3u --rtp 上海市电信.txt \
    --rtp-dir source/zubo/rtp -f m3u

# 使用自定义配置文件
python zubo/m3u_parser.py input.m3u --rtp 广东电信.txt \
    --config source/zubo/data.py -f m3u
```

### 4. 比较两个M3U文件

```bash
# 基本比较（控制台输出）
python zubo/M3U_Kit.py file1.m3u --compare file2.m3u

# 生成详细报告
python zubo/M3U_Kit.py file1.m3u --compare file2.m3u \
    --compare-output diff_report.txt
```

### 5. 批量处理M3U文件

```bash
# 批量处理目录中的所有M3U文件，自动补充Logo
python zubo/M3U_Kit.py --batch-m3u --input-dir m3u --output-dir m3u_processed

# 批量处理并启用去重功能
python zubo/M3U_Kit.py --batch-m3u --input-dir m3u --output-dir m3u_processed --dedup
```

### 6. URL去重

```bash
# 去除重复的URL（保留第一个出现的，优先保留有logo的）
python zubo/M3U_Kit.py input.m3u --dedup -f m3u -o output.m3u
```

### 7. 批量处理RTP文件

```bash
# 使用模板M3U文件批量处理所有RTP文件
python zubo/M3U_Kit.py template.m3u --batch --rtp-dir source/zubo/rtp --output-dir m3u
```

## 命令行参数

### 必需参数

- `input_file`: 输入的M3U文件路径

### 可选参数

#### 输出选项

- `-o, --output`: 输出文件路径（可选）
- `-f, --format {json,csv,m3u}`: 输出格式（默认：json）
- `-s, --summary`: 显示解析摘要信息

#### RTP合并选项

- `--rtp`: RTP文件路径（相对于rtp目录，如：`上海市电信.txt`）
- `--rtp-dir`: RTP文件目录（默认：`source/zubo/rtp`）
- `--config`: 配置文件路径（默认：`source/zubo/data.py`）

#### 比较选项

- `--compare`: 要比较的第二个M3U文件路径
- `--compare-output`: 比较结果输出文件路径（可选）

#### 批量处理选项

- `--batch-m3u`: 批量处理M3U文件模式（从input-dir读取所有m3u文件，处理后输出到output-dir）
- `--input-dir`: 批量处理M3U时的输入目录
- `--batch`: 批量处理RTP文件模式（处理rtp-dir中所有txt文件）
- `--output-dir`: 批量处理时的输出目录（默认：`m3u`）
- `--report`: 批量处理时输出缺少logo的频道报告文件路径

#### 其他选项

- `--dedup`: 去除重复的URL（保留第一个出现的，优先保留有logo的）

## 功能详解

### 1. M3U文件解析

工具可以解析标准的M3U播放列表文件，提取以下信息：

- **tvg-id**: 频道ID
- **tvg-name**: 频道标准名称
- **tvg-logo**: 频道Logo URL
- **group-title**: 频道分组
- **channel-name**: 频道显示名称
- **url**: 播放地址

### 2. RTP文件合并

合并功能会：

1. **匹配频道**：根据`tvg-name`匹配M3U和RTP文件中的频道
2. **替换URL**：使用RTP文件中的URL替换M3U中的URL（保持原始格式）
3. **标准化名称**：通过配置文件将频道名标准化
4. **重新分组**：根据配置文件的分类重新组织`group-title`
5. **添加新频道**：将RTP文件中未匹配的频道添加到M3U末尾
6. **重新编号**：按原顺序重新编号`tvg-id`

**重要特性**：
- 保留原M3U文件的频道顺序
- 保留原`channel-name`（如果存在）
- URL保持RTP文件中的原始格式（不进行转换）

### 3. URL比较功能

比较功能可以：

- 找出两个M3U文件中URL不同的频道
- 识别仅在某个文件中存在的频道
- 统计URL相同的频道
- 生成详细的差异报告

比较时会自动使用配置文件中的频道名映射，将不同格式的频道名（如"CCTV1"和"CCTV-1"）识别为同一频道。

### 4. 自动补充Logo功能

当导出M3U文件时，如果频道的`tvg-logo`为空，工具会自动尝试从以下两个在线源获取Logo：

1. `https://epg.112114.xyz/logo/{tvg-name}.png`
2. `https://live.fanmingming.com/tv/{tvg-name}.png`

**工作原理**：
- 按顺序尝试两个URL
- 先尝试原始`tvg-name`（兼容特殊字符如`CCTV5+`）
- 如果失败，尝试URL编码后的名称
- 如果找到可访问的Logo，自动补充到`tvg-logo`字段

**注意事项**：
- 需要网络连接
- 每个URL检查超时时间为5秒
- 批量处理时可能需要较长时间

### 5. 批量处理功能

#### 批量处理M3U文件

批量处理模式可以：
- 读取输入目录中的所有`.m3u`文件
- 自动补充缺失的Logo
- 可选启用URL去重
- 输出到指定目录，保持原文件名

**使用场景**：
- 批量更新多个M3U文件的Logo
- 批量去重多个M3U文件
- 批量格式转换

#### 批量处理RTP文件

批量处理RTP模式可以：
- 使用模板M3U文件
- 批量合并多个RTP文件
- 生成对应的M3U文件
- 生成缺少Logo的频道报告

### 6. URL去重功能

去重功能可以：
- 识别重复的URL
- 保留第一个出现的频道
- 优先保留有Logo的频道（如果存在重复）
- 生成去重统计报告

### 7. 配置文件说明

配置文件（默认：`source/zubo/data.py`）包含：

- **CHANNEL_CATEGORIES**: 频道分类配置
  ```python
  CHANNEL_CATEGORIES = {
      "央视频道": ["CCTV1", "CCTV2", ...],
      "卫视频道": ["湖南卫视", "浙江卫视", ...],
      ...
  }
  ```

- **CHANNEL_MAPPING**: 频道名映射配置
  ```python
  CHANNEL_MAPPING = {
      "CCTV1": ["CCTV-1", "CCTV-1 HD", "CCTV1 HD", ...],
      "CCTV2": ["CCTV-2", "CCTV-2 HD", ...],
      ...
  }
  ```

## 使用示例

### 示例1：解析并查看统计信息

```bash
python zubo/M3U_Kit.py backup/武汉-电信.m3u -s
```

输出：
```
✅ 成功解析 112 个频道

📊 解析摘要:
  总频道数: 112
  有tvg-name的频道: 111
  有tvg-logo的频道: 111
  有URL的频道: 112

📁 分组统计:
  央视: 27
  卫视: 36
  ...
```

### 示例2：合并RTP文件

```bash
python zubo/M3U_Kit.py backup/武汉-电信.m3u \
    --rtp 湖北电信.txt \
    -f m3u \
    -o backup/武汉-电信_merged.m3u \
    -s
```

输出：
```
✅ 成功解析 112 个频道

🔄 正在合并RTP文件: 湖北电信.txt
✅ 合并完成，共 127 个频道（包含新增的RTP频道）

📊 解析摘要:
  总频道数: 127
  ...
```

### 示例3：比较两个M3U文件

```bash
python zubo/M3U_Kit.py backup/武汉-电信.m3u \
    --compare backup/武汉-电信_merged.m3u \
    --compare-output diff_report.txt
```

### 示例4：批量处理M3U文件并补充Logo

```bash
python zubo/M3U_Kit.py --batch-m3u --input-dir m3u --output-dir m3u_processed
```

输出：
```
📋 找到 43 个M3U文件
📁 输入目录: m3u
📁 输出目录: m3u_processed

🔄 正在处理: 北京移动.m3u
  ✅ 完成: 161 个频道，补充了 15 个logo
🔄 正在处理: 河北联通.m3u
  ✅ 完成: 61 个频道，补充了 8 个logo
...

📊 批量处理完成:
  ✅ 成功: 43 个文件
  ❌ 失败: 0 个文件
  📺 总频道数: 4500
  🖼️  补充logo数: 320
```

### 示例5：批量处理并去重

```bash
python zubo/M3U_Kit.py --batch-m3u --input-dir m3u --output-dir m3u_processed --dedup
```

### 示例6：导出M3U并自动补充Logo

```bash
python zubo/M3U_Kit.py input.m3u -f m3u -o output.m3u
```

导出时会自动检查并补充缺失的Logo。

输出：
```
🔍 正在比较两个M3U文件...
  文件1: backup/武汉-电信.m3u
  文件2: backup/武汉-电信_merged.m3u

📊 比较结果:
  文件1总频道数: 112
  文件2总频道数: 127
  ✅ URL相同的频道: 0
  ⚠️  URL不同的频道: 111
  📄 仅在文件1中的频道: 0
  📄 仅在文件2中的频道: 15
```

## 输出格式说明

### JSON格式

```json
{
  "header": {
    "name": "武汉电信IPTV",
    "x-tvg-url": "..."
  },
  "channels": [
    {
      "tvg-id": "1",
      "tvg-name": "CCTV1",
      "tvg-logo": "https://...",
      "group-title": "央视频道",
      "channel-name": "CCTV1综合",
      "url": "rtp://..."
    }
  ]
}
```

### CSV格式

包含列：`tvg-name`, `tvg-logo`, `tvg-id`, `group-title`, `channel-name`, `url`

### M3U格式

标准M3U播放列表格式：
```
#EXTM3U name="武汉电信IPTV"
#EXTM3U x-tvg-url="..."
#EXTINF:-1,tvg-id="1" tvg-name="CCTV1" tvg-logo="..." group-title="央视频道",CCTV1综合
rtp://239.254.96.96:8550
```

## 常见问题

### Q: RTP文件格式是什么？

A: RTP文件是文本文件，每行格式为：`频道名,rtp://地址`，例如：
```
CCTV1,rtp://239.254.96.96:8550
CCTV2,rtp://239.69.1.102:10250
```

### Q: 如何添加新的频道映射？

A: 编辑配置文件（`source/zubo/data.py`），在`CHANNEL_MAPPING`中添加映射：
```python
CHANNEL_MAPPING = {
    "标准名": ["别名1", "别名2", ...],
    ...
}
```

### Q: 合并后为什么有些频道没有匹配？

A: 可能原因：
1. RTP文件中的频道名不在映射配置中
2. M3U中的频道名无法映射到标准名
3. 未匹配的频道会被添加到M3U末尾（tvg-logo为空）

### Q: 如何保持原M3U文件的顺序？

A: 工具默认保持原M3U文件的顺序，不会重新排序。新增的RTP频道会追加到末尾。

### Q: 自动补充Logo功能如何工作？

A: 当导出M3U文件时，如果`tvg-logo`为空，工具会：
1. 使用`tvg-name`构建两个可能的Logo URL
2. 依次检查URL是否可以访问（HEAD请求）
3. 如果找到可访问的Logo，自动补充到`tvg-logo`字段
4. 如果两个URL都不可访问，保持为空

### Q: 批量处理需要多长时间？

A: 处理时间取决于：
- 文件数量和大小
- 需要补充Logo的频道数量
- 网络连接速度
- 每个URL检查超时时间为5秒

建议在批量处理大量文件时耐心等待。

### Q: 如何只处理单个文件而不批量处理？

A: 不使用`--batch-m3u`参数，直接指定单个文件即可：
```bash
python zubo/M3U_Kit.py input.m3u -f m3u -o output.m3u
```

### Q: 去重功能如何选择保留哪个频道？

A: 去重功能按以下优先级：
1. 保留第一个出现的频道
2. 如果存在重复，优先保留有Logo的频道
3. 如果都有Logo或都没有Logo，保留第一个出现的

## 代码结构

工具采用模块化设计，主要类：

- **M3UPlaylist**: 主播放列表处理器
- **ChannelConfigLoader**: 配置加载器
- **RTPFileLoader**: RTP文件加载器
- **ChannelMapper**: 频道名称映射器
- **M3UComparator**: M3U文件比较器

## 版本信息

- 版本：2.1
- 更新日期：2024
- Python要求：3.6+

### 更新日志

#### v2.1 (2024)
- ✨ 新增自动补充Logo功能
- ✨ 新增批量处理M3U文件功能
- ✨ 新增URL去重功能
- 📝 更新文档和使用示例

#### v2.0 (2024)
- 🔄 重构代码结构
- ✨ 新增RTP文件合并功能
- ✨ 新增URL比较功能
- ✨ 支持多格式导出

## 许可证

本工具为项目内部工具，遵循项目许可证。

