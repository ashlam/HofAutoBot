from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

# 预设64种颜色
PREDEFINED_COLORS: List[Tuple[str, str]] = [
    # 红色系
    ("#FF0000", "红色"),
    ("#FF4500", "橙红色"),
    ("#FF6347", "番茄红"),
    ("#DC143C", "猩红色"),
    ("#CD5C5C", "印度红"),
    ("#B22222", "火砖红"),
    ("#8B0000", "深红色"),
    ("#800000", "栗色"),
    
    # 橙色系
    ("#FFA500", "橙色"),
    ("#FF8C00", "深橙色"),
    ("#FFD700", "金色"),
    ("#DAA520", "金菊色"),
    ("#B8860B", "深金色"),
    ("#D2691E", "巧克力色"),
    ("#A0522D", "赭色"),
    ("#8B4513", "马鞍棕色"),
    
    # 黄色系
    ("#FFFF00", "黄色"),
    ("#FFE4B5", "莫吉托"),
    ("#F0E68C", "卡其色"),
    ("#EEE8AA", "苍麦色"),
    ("#BDB76B", "深卡其色"),
    ("#F5DEB3", "小麦色"),
    ("#DEB887", "实木色"),
    ("#D2B48C", "茶色"),
    
    # 绿色系
    ("#00FF00", "绿色"),
    ("#32CD32", "酸橙绿"),
    ("#98FB98", "淡绿色"),
    ("#90EE90", "淡海绿"),
    ("#3CB371", "中海绿"),
    ("#2E8B57", "海绿色"),
    ("#228B22", "森林绿"),
    ("#006400", "深绿色"),
    
    # 青色系
    ("#00FFFF", "青色"),
    ("#E0FFFF", "淡青色"),
    ("#AFEEEE", "淡绿松石"),
    ("#7FFFD4", "碧绿色"),
    ("#40E0D0", "绿松石"),
    ("#48D1CC", "中绿松石"),
    ("#00CED1", "深青色"),
    ("#008B8B", "深青绿"),
    
    # 蓝色系
    ("#0000FF", "蓝色"),
    ("#1E90FF", "道奇蓝"),
    ("#87CEEB", "天蓝色"),
    ("#4169E1", "皇家蓝"),
    ("#0000CD", "中蓝色"),
    ("#00008B", "深蓝色"),
    ("#000080", "海军蓝"),
    ("#191970", "午夜蓝"),
    
    # 紫色系
    ("#8A2BE2", "紫罗兰"),
    ("#9400D3", "深紫色"),
    ("#9370DB", "中紫色"),
    ("#BA55D3", "兰花紫"),
    ("#DDA0DD", "李子色"),
    ("#EE82EE", "紫罗兰色"),
    ("#FF00FF", "品红色"),
    ("#FF1493", "深粉色"),
    
    # 灰白色系
    ("#FFFFFF", "白色"),
    ("#F5F5F5", "白烟色"),
    ("#DCDCDC", "浅灰色"),
    ("#D3D3D3", "淡灰色"),
    ("#C0C0C0", "银色"),
    ("#A9A9A9", "暗灰色"),
    ("#808080", "灰色"),
    ("#000000", "黑色")
]

@dataclass
class Tag:
    id: str  # 使用UUID作为标签的唯一标识
    name: str
    color: str  # 颜色值，格式为 #RRGGBB
    tag_id: str  # 用户定义的标签ID

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tag':
        return cls(
            id=data['id'],
            name=data['name'],
            color=data['color'],
            tag_id=data.get('tag_id', '')  # 兼容旧数据
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'tag_id': self.tag_id
        } 