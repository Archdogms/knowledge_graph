#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文化典籍文本NER实体抽取与结构化工具（文化锚定版）
从OCR文本中提取 **文化载体相关** 实体，过滤掉与文化旅游无关的一般性词汇

核心改进（相对上一版）：
    1. 加载 cultural_anchors.json（165条政府普查级文化载体锚点）自动注入词典
    2. 彻底取消"其他"类实体 —— 只保留明确归类为6类文化实体的词条
    3. 锚点名称在实体输出中标注 is_anchor=True，供下游知识图谱优先选用

研究方法：
    "jieba分词 + 自定义词典 + 文化锚点表 + 后缀规则"的轻量级NER方案。
    
    处理流程：
    1. 加载全部文本源（每个限500,000字符）
    2. 注入自定义词典（6类 + 锚点表，共400+个领域术语）
    3. jieba.cut分词 → 类型判定 → 未归类则丢弃（不再保留"其他"）
    4. TF-IDF计算 + 多源合并 + 共现关系提取
    
    输出：
    - culture_entities.json：纯文化实体库（无"其他"类）
    - culture_relations.json：共现关系库
"""

import os
import re
import json
import math
from collections import Counter, defaultdict

try:
    import jieba
    import jieba.posseg as pseg
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False
    print("[警告] 未安装jieba，将使用正则提取模式。建议: pip install jieba")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "database")

# ── 加载文化载体锚点表 ──
ANCHOR_NAMES = set()
ANCHOR_DICT = {}

def _load_anchors():
    """从 cultural_anchors.json 加载锚点名称，自动注入自定义词典"""
    global ANCHOR_NAMES, ANCHOR_DICT
    anchor_path = os.path.join(OUTPUT_DIR, "cultural_anchors.json")
    if not os.path.exists(anchor_path):
        print("[INFO] 未找到 cultural_anchors.json，跳过锚点注入")
        return
    with open(anchor_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for a in data.get("anchors", []):
        name = a["name"]
        if len(name) >= 2:
            ANCHOR_NAMES.add(name)
            atype = a.get("anchor_type", "")
            if "文物" in atype or "古" in atype:
                ANCHOR_DICT[name] = "建筑"
            elif "非遗" in atype:
                ANCHOR_DICT[name] = "文化要素"
            elif "景观" in atype:
                ANCHOR_DICT[name] = "地点"
            elif "村" in atype or "名镇" in atype:
                ANCHOR_DICT[name] = "地点"
            elif "圩" in atype or "街" in atype:
                ANCHOR_DICT[name] = "地点"
            else:
                ANCHOR_DICT[name] = "建筑"
    print(f"[INFO] 加载文化锚点: {len(ANCHOR_NAMES)} 个")

CUSTOM_DICT = {
    "人物": [
        # 武术人物
        "黄飞鸿", "叶问", "梁赞", "陈华顺", "张炎", "李小龙", "黄麒英",
        "陆正刚", "林世荣", "梁宽", "凌云阶", "鬼脚七",
        # 政治/学术人物
        "康有为", "梁启超", "戴鸿慈", "陈启沅", "詹天佑", "邹伯奇",
        "区梦觉", "区大原", "区大典", "区谓良", "区维翰", "区新", "区次颜", "区世来",
        "方献夫", "湛若水", "霍韬", "陈献章", "庞嵩", "霍冀", "冯了性",
        "伦文叙", "吴荣光", "朱次琦", "简朝亮", "桂文灿",
        # 明清/近代名人
        "石景宜", "傅德用", "傅老榕", "韩雍", "葛洪", "陆云从",
        "黄少强", "黄君璧", "林良", "冯乃超", "陈铁军",
        "张国英", "肖跃华", "潘侣生", "罗格", "冼玉清",
        # 孔氏家族
        "孔纬", "孔昌弟", "孔承休", "孔公通", "孔昭熙",
        # 陈启沅关联
        "陈启枢", "陈蒲生", "招雨田",
    ],
    "地点": [
        # 行政区划
        "南海区", "南海", "佛山", "佛山市", "广东", "广州",
        "西樵镇", "九江镇", "丹灶镇", "狮山镇", "大沥镇", "里水镇", "桂城街道",
        "平洲", "盐步", "官窑", "罗村", "小塘", "松岗", "黄岐", "和顺",
        # 山水景观
        "西樵山", "千灯湖", "映月湖", "贤鲁岛", "南国桃园", "听音湖",
        "天湖", "翠岩", "白云洞", "碧玉洞", "石燕岩", "九龙岩",
        # 古村落
        "松塘村", "孔村", "烟桥村", "仙岗村", "西城村", "银坑村", "简村",
        "茶基村", "显纲村", "上林村", "颜边村", "沙咀村", "华平村",
        "云路村", "大科村", "白山村", "石排村", "寺边村", "云端村",
        "逢涌村", "璜矶村", "叠滘村", "深村", "罗行村",
        # 历史地名
        "珠江三角洲", "岭南", "南雄", "珠玑巷", "西江", "北江",
        "桑园围", "吉利围", "沙头", "江浦", "民乐", "朗星",
    ],
    "建筑": [
        # 通用建筑类型
        "祖庙", "宗祠", "祠堂", "书院", "牌坊", "炮楼", "门楼", "镬耳屋",
        # 书院
        "云谷书院", "大科书院", "石泉书院", "四峰书院",
        "孔林书院", "三湖书院", "白山书院", "应元书院",
        # 宗祠家庙
        "至圣家庙", "明德堂", "敦伦堂", "世德堂", "崇德堂",
        "韩都宪祠", "传氏宗祠", "梁氏宗祠", "马氏宗祠",
        "陈氏宗祠", "李氏宗祠", "黄氏宗祠", "潘氏宗祠",
        "何氏宗祠", "邓氏宗祠", "关氏宗祠", "区氏宗祠",
        "吴氏宗祠", "罗氏宗祠", "简氏宗祠",
        # 宗教建筑
        "天后宫", "宝峰寺", "观音寺", "北帝庙", "南海神庙",
        "云泉仙馆", "紫姑庙", "三圣宫", "华光庙",
        # 纪念馆/博物馆
        "黄飞鸿纪念馆", "康有为故居", "区梦觉故居",
        "南海博物馆", "南海影视城", "九江双蒸博物馆",
        "陈启沅纪念馆", "邹伯奇纪念馆", "詹天佑故居",
        "石景宜艺术馆", "黄少强纪念馆", "冯了性药铺",
    ],
    "文化要素": [
        # 武术
        "醒狮", "龙舟", "咏春拳", "洪拳", "白眉拳", "蔡李佛拳",
        "武术", "龙狮", "狮舞", "南拳", "功夫", "太极",
        # 音乐戏曲
        "粤曲", "粤剧", "十番音乐", "龙舟说唱", "咸水歌", "木鱼书",
        # 传统工艺
        "藤编", "灰塑", "剪纸", "金箔", "缫丝", "竹编", "木雕",
        "刺绣", "石湾陶", "广绣", "广彩", "香云纱",
        # 饮食文化
        "九江双蒸酒", "煎堆", "鱼花", "酱油", "盲公饼",
        "伦教糕", "大良蹦砂", "均安蒸猪", "桑果酒",
        # 学术文化
        "科举", "翰林", "进士", "举人", "书院", "理学", "心学",
        # 民俗
        "花灯", "生菜会", "赛龙舟", "龙母诞", "北帝诞", "出色巡游",
        "锦龙盛会", "老龙礼俗", "秋色", "行通济",
        # 产业文化
        "缫丝业", "蚕桑", "丝织", "纺织", "制陶", "铸造",
        # 综合
        "非遗", "非物质文化遗产", "岭南文化", "广府文化",
    ],
    "事件": [
        "开村", "建村", "祭祖", "重修", "扩建", "迁徙",
        "科举考试", "进士及第", "戊戌变法", "辛亥革命",
        "省港大罢工", "北伐战争", "抗日战争",
        "出色巡游", "弯道赛龙船", "老龙礼俗",
        "公车上书", "百日维新", "洋务运动", "鸦片战争",
        "继昌隆缫丝厂", "土地改革", "改革开放",
    ],
    "朝代": [
        "唐代", "宋代", "元代", "明代", "清代", "民国",
        "南宋", "北宋", "东晋", "南北朝", "隋代",
        "康熙", "乾隆", "嘉庆", "道光", "咸丰", "同治", "光绪", "宣统",
        "正德", "嘉靖", "永乐", "洪武", "万历", "天启", "崇祯",
        "顺治", "雍正",
    ],
}


STOP_WORDS = {
    "我们", "他们", "她们", "它们", "这个", "那个", "自己", "什么", "这些", "那些",
    "一个", "一些", "一种", "没有", "已经", "可以", "不是", "就是", "如果", "或者",
    "因为", "所以", "但是", "而且", "虽然", "不过", "然而", "于是", "以及", "以后",
    "这样", "那样", "怎样", "为什么", "进行", "通过", "根据", "按照", "关于", "对于",
    "比较", "非常", "十分", "特别", "其中", "之后", "之前", "以来", "之间", "以上",
    "以下", "左右", "前后", "同时", "当时", "目前", "现在", "其他", "部分", "情况",
    "问题", "方面", "工作", "发展", "建设", "管理", "组织", "活动", "教育", "生产",
    "经济", "社会", "群众", "人民", "单位", "企业", "学校", "地区", "全国", "中国",
    "中央", "国家", "政府", "领导", "干部", "同志", "委员", "委员会", "主任", "副主任",
    "主席", "副主席", "书记", "副书记", "成立", "开始", "结束", "继续", "参加", "研究",
    "提出", "认为", "表示", "指出", "要求", "决定", "实现", "完成", "处理", "解决",
    "增加", "减少", "提高", "加强", "保持", "恢复", "改善", "培养", "利用", "采取",
    "应该", "必须", "需要", "希望", "可能", "不能", "能够", "一定", "有关", "有些",
    "各种", "大量", "许多", "大家", "还是", "只是", "而是", "不但", "不仅", "即使",
    "第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十",
    "也是", "更是", "正是", "又是", "则是", "也有", "又有", "还有", "并且", "另外",
    "是否", "否则", "总之", "反正", "一般", "主要", "一直", "其实", "当然", "至少",
    "几乎", "尤其", "往往", "通常", "显然", "或许", "逐渐", "不断", "重新", "正在",
    "曾经", "仍然", "一方", "中共", "政协", "人大", "全省", "全市", "全县", "办公室",
    "每年", "每月", "每天", "年月", "月日", "年度", "时期", "时间", "过程", "条件",
    "标准", "原则", "方法", "技术", "设备", "材料", "产品", "资金", "制度", "计划",
    "方案", "意见", "报告", "会议", "文件", "规定", "措施", "任务", "目标", "效果",
    "作用", "影响", "水平", "能力", "质量", "数量", "面积", "人口", "万元", "人次",
    "以前", "后来", "此后", "然后", "期间", "同年", "次年", "翌年", "去年", "今年",
}

def load_text_files(max_chars_per_file=500000):
    """加载所有典籍文本，限制单文件最大字符数以确保处理效率"""
    texts = {}
    text_dir = os.path.join(DATA_DIR, "典籍文本")

    ocr_file = os.path.join(text_dir, "南海县志_OCR连续文本.txt")
    if os.path.exists(ocr_file):
        with open(ocr_file, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file]
        texts["南海县志(OCR)"] = content

    subdir = os.path.join(text_dir, "开题阶段典籍")
    if os.path.exists(subdir):
        for fname in os.listdir(subdir):
            if fname.endswith(".md"):
                fpath = os.path.join(subdir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 500:
                    if len(content) > max_chars_per_file:
                        content = content[:max_chars_per_file]
                    texts[fname.replace(".md", "")] = content

    nanhai_dir = os.path.join(text_dir, "南海文史资料")
    if os.path.exists(nanhai_dir):
        for fname in os.listdir(nanhai_dir):
            if fname.endswith(".txt"):
                fpath = os.path.join(nanhai_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 500:
                    if len(content) > max_chars_per_file:
                        content = content[:max_chars_per_file]
                    texts[fname.replace(".txt", "")] = content

    return texts


def init_jieba():
    """初始化jieba并加载自定义词典 + 锚点词典"""
    if not HAS_JIEBA:
        return

    for category, words in CUSTOM_DICT.items():
        for word in words:
            jieba.add_word(word, freq=1000)

    for name in ANCHOR_NAMES:
        jieba.add_word(name, freq=1000)


def extract_entities_jieba(text, source_name, top_n=300):
    """使用jieba分词提取实体（使用jieba.cut代替pseg以提升速度）"""
    words_raw = jieba.cut(text)
    entity_counter = Counter()

    for word in words_raw:
        if len(word) < 2 or len(word) > 8:
            continue
        if not re.search(r'[\u4e00-\u9fff]', word):
            continue
        if word in STOP_WORDS:
            continue
        entity_counter[word] += 1

    entities = {}
    total_words = sum(entity_counter.values())

    for word, freq in entity_counter.most_common(top_n):
        if freq < 2:
            continue

        entity_type = "其他"
        confidence = 0.5

        for category, keywords in CUSTOM_DICT.items():
            if word in keywords:
                entity_type = category
                confidence = 0.95
                break

        if entity_type == "其他" and word in ANCHOR_DICT:
            entity_type = ANCHOR_DICT[word]
            confidence = 0.9

        if entity_type == "其他":
            if re.match(r'.*(?:村|镇|区|市|县|街|路|山|岛|湖|江|河|洲|岗|塘|围|涌|窖|圩|墟)$', word):
                entity_type = "地点"
                confidence = 0.8
            elif re.match(r'.*(?:代|朝|年间|年)$', word) and len(word) <= 4:
                entity_type = "朝代"
                confidence = 0.8
            elif re.match(r'.*(?:祠|庙|寺|院|堂|馆|楼|坊|塔|桥|亭|阁|庵|宫|殿|墓|庐|园|台|坛)$', word):
                entity_type = "建筑"
                confidence = 0.8
            elif re.match(r'.*(?:拳|舞|歌|曲|戏|艺|编|绣|塑|雕|陶|瓷|画|锻|染|织|酿)$', word):
                entity_type = "文化要素"
                confidence = 0.75
            elif re.match(r'.*(?:先生|公|氏|翁|侯|侍郎|尚书|知县|县令|总督|巡抚|提督|状元|太守)$', word) and 2 <= len(word) <= 5:
                entity_type = "人物"
                confidence = 0.7

        if entity_type == "其他":
            continue

        tf = freq / total_words if total_words > 0 else 0
        idf = math.log(total_words / freq) if freq > 0 else 0

        entities[word] = {
            "type": entity_type,
            "mentions": freq,
            "tfidf": round(tf * idf, 6),
            "confidence": confidence,
            "source": source_name,
        }

    return entities


def extract_entities_regex(text, source_name, top_n=300):
    """使用正则表达式提取实体（备选方案）"""
    words = re.findall(r'[\u4e00-\u9fa5]{2,8}', text)
    word_counts = Counter(words)

    entities = {}
    total_words = sum(word_counts.values())

    for word, freq in word_counts.most_common(top_n):
        if freq < 3:
            continue

        entity_type = "其他"
        confidence = 0.5

        for category, keywords in CUSTOM_DICT.items():
            if word in keywords:
                entity_type = category
                confidence = 0.95
                break

        if entity_type == "其他" and word in ANCHOR_DICT:
            entity_type = ANCHOR_DICT[word]
            confidence = 0.9

        if entity_type == "其他":
            if re.match(r'.*(?:村|镇|区|市|县|街|路|山|岛|湖|江|河|洲|岗|塘|围|涌)$', word):
                entity_type = "地点"
                confidence = 0.8
            elif re.match(r'.*(?:代|朝|年间)$', word):
                entity_type = "朝代"
                confidence = 0.8
            elif re.match(r'.*(?:祠|庙|寺|院|堂|馆|楼|坊|塔|桥|亭|阁|庵|宫|殿|墓|园|台)$', word):
                entity_type = "建筑"
                confidence = 0.8
            elif re.match(r'.*(?:拳|舞|歌|曲|戏|艺|编|绣|塑|雕|陶|瓷|画|锻|染|织|酿)$', word):
                entity_type = "文化要素"
                confidence = 0.75
            elif re.match(r'.*(?:先生|公|氏|翁)$', word) and 2 <= len(word) <= 5:
                entity_type = "人物"
                confidence = 0.7

        if entity_type == "其他":
            continue

        tf = freq / total_words if total_words > 0 else 0
        idf = math.log(total_words / freq) if freq > 0 else 0

        entities[word] = {
            "type": entity_type,
            "mentions": freq,
            "tfidf": round(tf * idf, 6),
            "confidence": confidence,
            "source": source_name,
        }

    return entities


def merge_entities(all_entities_by_source):
    """合并多源实体，计算综合权重"""
    merged = {}

    for source_name, entities in all_entities_by_source.items():
        for name, info in entities.items():
            if name in merged:
                merged[name]["mentions"] += info["mentions"]
                merged[name]["sources"].append(source_name)
                if info["confidence"] > merged[name]["confidence"]:
                    merged[name]["confidence"] = info["confidence"]
                    merged[name]["type"] = info["type"]
            else:
                merged[name] = {
                    "type": info["type"],
                    "mentions": info["mentions"],
                    "confidence": info["confidence"],
                    "sources": [source_name],
                }

    for name, info in merged.items():
        info["source_count"] = len(info["sources"])
        info["cross_source_weight"] = info["mentions"] * (1 + 0.3 * (info["source_count"] - 1))

    return merged


def extract_relations(text, entities, max_relations=5000):
    """提取实体间的共现关系"""
    sentences = re.split(r'[。！？；\n]', text)
    entity_names = set(entities.keys())

    relations = []
    rel_counter = Counter()

    for sentence in sentences:
        if len(sentence) < 10:
            continue

        found = [e for e in entity_names if e in sentence]
        if len(found) < 2:
            continue

        for i in range(min(len(found), 6)):
            for j in range(i + 1, min(len(found), 6)):
                pair = tuple(sorted([found[i], found[j]]))
                rel_counter[pair] += 1

    for (e1, e2), count in rel_counter.most_common(max_relations):
        if count < 2:
            break
        relations.append({
            "entity1": e1,
            "entity2": e2,
            "co_occurrence": count,
            "type1": entities[e1]["type"],
            "type2": entities[e2]["type"],
        })

    return relations


def save_database(entities, relations):
    """保存为结构化数据库"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    entity_list = []
    for i, (name, info) in enumerate(
        sorted(entities.items(), key=lambda x: x[1]["cross_source_weight"], reverse=True)
    ):
        entity_list.append({
            "id": f"E{i+1:04d}",
            "name": name,
            "type": info["type"],
            "mentions": info["mentions"],
            "confidence": info["confidence"],
            "source_count": info["source_count"],
            "sources": info["sources"],
            "weight": round(info["cross_source_weight"], 2),
            "is_anchor": name in ANCHOR_NAMES,
        })

    entity_path = os.path.join(OUTPUT_DIR, "culture_entities.json")
    with open(entity_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(entity_list),
            "type_stats": dict(Counter(e["type"] for e in entity_list)),
            "entities": entity_list,
        }, f, ensure_ascii=False, indent=2)
    print(f"文化实体库: {entity_path} ({len(entity_list)} 个实体)")

    name_to_id = {e["name"]: e["id"] for e in entity_list}
    rel_list = []
    for r in relations:
        if r["entity1"] in name_to_id and r["entity2"] in name_to_id:
            rel_list.append({
                "source_id": name_to_id[r["entity1"]],
                "target_id": name_to_id[r["entity2"]],
                "source_name": r["entity1"],
                "target_name": r["entity2"],
                "co_occurrence": r["co_occurrence"],
                "source_type": r["type1"],
                "target_type": r["type2"],
            })

    rel_path = os.path.join(OUTPUT_DIR, "culture_relations.json")
    with open(rel_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(rel_list),
            "relations": rel_list,
        }, f, ensure_ascii=False, indent=2)
    print(f"关系库: {rel_path} ({len(rel_list)} 条关系)")

    return entity_list, rel_list


def main():
    print("=" * 60)
    print("文化典籍NER实体抽取")
    print("=" * 60)

    _load_anchors()

    if HAS_JIEBA:
        init_jieba()
        print("使用jieba分词模式")
    else:
        print("使用正则提取模式")

    print("\n--- 加载文本 ---")
    texts = load_text_files()
    print(f"共加载 {len(texts)} 个文本文件")
    for name, text in texts.items():
        print(f"  {name}: {len(text)} 字符")

    print("\n--- 实体抽取 ---")
    all_entities = {}
    all_text = ""

    for name, text in texts.items():
        print(f"处理: {name}...")
        if HAS_JIEBA:
            entities = extract_entities_jieba(text, name)
        else:
            entities = extract_entities_regex(text, name)
        print(f"  提取 {len(entities)} 个实体")
        all_entities[name] = entities
        all_text += text + "\n"

    print("\n--- 实体合并 ---")
    merged = merge_entities(all_entities)
    print(f"合并后: {len(merged)} 个独立实体")

    type_stats = Counter(info["type"] for info in merged.values())
    for t, c in type_stats.most_common():
        print(f"  {t}: {c}")

    print("\n--- 关系提取 ---")
    relations = extract_relations(all_text, merged)
    print(f"提取 {len(relations)} 条共现关系")

    print("\n--- 保存数据库 ---")
    save_database(merged, relations)

    print("\n完成！")


if __name__ == "__main__":
    main()
