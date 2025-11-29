# M3U播放列表处理工具
* 可以输入多个目录，将文件名（不含后缀）相同的文件相合并，可以是txt文件，也可以是m3u文件。
* 解析：自动根据文件后缀解析文件，txt后缀文件是csv格式，第一列是tvg-name，第二列是url,当url以#开头时忽略该行，当url以#分割两url时拆为两条url记录。m3u后缀格式按照标准m3u格式解析，记住兼容两种情况。如：

```m3u
#EXTINF:-1 ,北京卫视4K
rtp://239.254.201.68:6000
#EXTINF:-1,tvg-id="26" tvg-name="北京卫视" tvg-logo="https://live.fanmingming.com/tv/北京卫视.png" group-title="卫视频道",北京卫视
rtp://239.3.1.241:8000
```
* 合并：使用url去重，url不重复的保留并合并所包含的信息，信息都完整时取先出现的，logo缺失时，调用代码补全logo
```
补全logo
```py
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
        
        return None
```

* 名称：CHANNEL_MAPPING中键为标准名称，值中的数组为别名，将tvg-name全都统一为标准名称。
* 分组：使用CHANNEL_CATEGORIES对频道进行分组，分组依据tvg-name
* 输出：将合并后的输出到单独的目录，输出的文件格式为M3U格式，文件最开始的两行内容：
```m3u
#EXTM3U name="湖南电信"
#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml,http://epg.51zmt.top:8000/e.xml"
```
其中第一行的"湖南电信"即是当前文件的文件名，第二行内容固定。

## 使用方法
合并两目录中的组播地址-仅合并两目录中都存在的
```shell
python M3U_Kit.py --input-dir "rtp" --input-dir "m3u" --output-dir "merged" --config "data.py"
```
合并两目录中的组播地址-包含不存在的
```shell
python M3U_Kit.py --input-dir "rtp" --input-dir "m3u" --output-dir "merged" --config "data.py" --convert-txt-to-m3u
```
## 详细缺失列表（按省市排序）：
 * 内蒙古移动.m3u
 * 吉林移动.m3u
 * 宁夏移动.m3u
 * 安徽联通.m3u
 * 广西移动.m3u
 * 广西联通.m3u
 * 新疆移动.m3u
 * 新疆联通.m3u
 * 江苏移动.m3u
 * 江苏联通.m3u
 * 江西移动.m3u
 * 江西联通.m3u
 * 浙江移动.m3u
 * 甘肃移动.m3u
 * 西藏移动.m3u
 * 西藏联通.m3u
 * 陕西联通.m3u
 * 青海移动.m3u