"""
小红书/公众号内容生成工具 - Python Web Server
使用方法: python3 server.py
然后浏览器打开 http://localhost:5188
"""

import json
import os
import re
import uuid
import urllib.request
import base64
from PIL import Image
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory, render_template_string

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

TOKLN_KEY = "sk-J2SuNvtu7MoGlHZhJQVHw9DonjbPBEr2dwsFX6GdQMcO3CZ9"
MINIMAX_KEY = "sk-cp-F87boPhlR8eSbEnOiZ6N1n769xoXMm2y7C9CoWEZt5Ib44u2BHcIboeDzu3Hm1sLCj587NJ2BhN_BCjy-AqpJkuhVPy0SJgxq-dzw8RZXiFd1VBZt19_QPU"
MINIMAX_URL = "https://api.minimax.chat/v1/chat/completions"
IMG_URL = "https://api.tokln.com/v1/images/generations"
UPLOAD_DIR = os.path.expanduser("~/Documents/Hermes/content-generator/uploads")
OUTPUT_DIR = os.path.expanduser("~/Documents/Hermes/content-generator/output")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# 图片分析：从参考图提取风格特征
# ──────────────────────────────────────────────

def analyze_image_style(img_data):
    """从图片提取颜色分布、亮度、氛围、构图特征"""
    try:
        img = Image.open(BytesIO(img_data)).convert("RGB")
        w, h = img.size
        img_small = img.resize((100, 100))

        # 提取主色调
        pixels = list(img_small.getdata())
        r_avg = sum(p[0] for p in pixels) // len(pixels)
        g_avg = sum(p[1] for p in pixels) // len(pixels)
        b_avg = sum(p[2] for p in pixels) // len(pixels)

        brightness = (r_avg + g_avg + b_avg) / 3

        # 判断冷暖
        if r_avg > g_avg + 10:
            temperature = "暖色调（红色/橙色）"
        elif b_avg > r_avg + 10:
            temperature = "冷色调（蓝色/紫色）"
        else:
            temperature = "中性色调"

        # 判断明暗
        if brightness > 180:
            lightness = "高亮度"
        elif brightness < 80:
            lightness = "低亮度，暗调"
        else:
            lightness = "中等亮度"

        # 判断饱和度
        saturation = sum(
            max(p) - min(p) for p in pixels
        ) // len(pixels)
        if saturation > 80:
            vibrancy = "高饱和度，鲜艳"
        elif saturation < 40:
            vibrancy = "低饱和度，莫兰迪/ins风"
        else:
            vibrancy = "中等饱和度"

        color_rgb = f"rgb({r_avg},{g_avg},{b_avg})"

        # 构图分析（边缘检测简化版）
        center_region = img_small.crop((20, 20, 80, 80))
        center_pixels = list(center_region.getdata())
        center_brightness = sum(sum(p)/3 for p in center_pixels) / len(center_pixels)
        edge_region = img_small.crop((0, 0, 100, 100))
        edge_pixels = list(edge_region.getdata())
        edge_brightness = sum(sum(p)/3 for p in edge_pixels) / len(edge_pixels)

        # 判断构图类型
        if center_brightness > edge_brightness + 15:
            composition = "中心聚焦型（主体在中间）"
        elif edge_brightness > center_brightness + 15:
            composition = "边缘暗角型（主体在中间，四周渐暗）"
        else:
            composition = "平铺均亮型（光线均匀分布）"

        # 判断画面情绪（基于颜色和亮度）
        if brightness > 150 and saturation > 60:
            mood = "明亮活泼、温暖愉悦"
        elif brightness < 100 and saturation > 60:
            mood = "强烈对比、戏剧张力"
        elif brightness < 100 and saturation < 50:
            mood = "沉稳内敛、电影感"
        elif brightness > 150 and saturation < 50:
            mood = "清新淡雅、文艺气质"
        else:
            mood = "自然平和、日常感"

        # 宽高比判断用途
        aspect = w / h if h > 0 else 1
        if aspect > 1.2:
            usage = "横版（风景/场景图）"
        elif aspect < 0.8:
            usage = "竖版（人物/产品图）"
        else:
            usage = "方版（INS风/头像）"

        return {
            "color_rgb": color_rgb,
            "temperature": temperature,
            "lightness": lightness,
            "vibrancy": vibrancy,
            "brightness": round(brightness, 1),
            "composition": composition,
            "mood": mood,
            "aspect_usage": usage,
            "style_hint": f"{lightness}，{vibrancy}，{temperature}，{mood}，{composition}"
        }
    except Exception as e:
        return {
            "color_rgb": "unknown",
            "temperature": "未知",
            "lightness": "未知",
            "vibrancy": "未知",
            "brightness": 128,
            "composition": "未知",
            "mood": "未知",
            "aspect_usage": "未知",
            "style_hint": ""
        }


# ──────────────────────────────────────────────
# 平台文案模板（升级版）
# ──────────────────────────────────────────────

PLATFORM_TEMPLATES = {
    "小红书": {
        "system": """你是一位千万粉丝的小红书头部创作者，擅长写让人"忍不住点进去"的种草笔记。

你的文案特点：
- 开头3句话必须有钩子：要么戳痛点、要么制造好奇、要么说出一个反常识的事实
- 中间像和闺蜜聊天，语气亲切自然，不生硬
- 善用"你品，你细品"、"救命"、"谁懂啊"这类口语化表达
- 适当留白，不把话说满
- 结尾有互动钩子，引导收藏/评论

风格底色：真实 > 精致，有温度 > 完美文笔

输出格式（严格按JSON返回，不要有任何其他内容）：
{
  "title": "标题，emoji开头，制造悬念或共鸣，20字以内",
  "hook": "开头3句话的钩子，引诱点进来",
  "body": "完整正文，有emoji，有段落，适合小红书阅读习惯",
  "tags": ["精准tag1", "精准tag2", "精准tag3", "精准tag4", "精准tag5"],
  "cover_style": "封面图的风格描述，结合参考图特征",
  "image_styles": ["配图1的具体画面描述，要和正文内容对应", "配图2的具体画面描述"],
  "call_to_action": "结尾引导互动的一句话",
  "tips": "发布建议，如封面构图、发布时间等"
}""",
        "model": "gpt-image-2",
        "category_prompts": True
    },
    "买手种草": {
        "system": """你是一位专业的小红书买手，擅长写高转化率的种草商单笔记，目标是让粉丝"看完就想买"。

买手文案核心逻辑：
- 开篇：场景共鸣 + 真实使用感，立刻建立信任
- 中段：成分/材质分析 → 对比测评（用前/用后、平替对比）→ 真实使用感受
- 结尾：精准购买引导，降低决策门槛
- 语气：真实用过才推荐，不夸张，但让人心动

转化导向结构（选最适合的）：
结构A「成分党型」：成分解析 → 科学背书 → 真实使用感 → 推荐指数
结构B「对比测评型」：痛点导入 → 3款对比（价格/使用感/效果）→ 优选推荐 → 购买链接引导
结构C「使用感受型」：场景共鸣 → 第一次用印象 → 持续使用变化 → 回购决定
结构D「平替替代型」：贵价痛点 → 找到平替 → 核心成分对比 → 省钱结论

结尾挂链引导必须包含：
- 购买理由总结（1-2句）
- 购买渠道提示（不说具体品牌，说"同款/同类"规避规则）
- 引导评论互动（"你们想看详细测评吗"）

输出格式（严格按JSON返回，不要有任何其他内容）：
{
  "title": "高点击率标题，emoji，制造悬念或共鸣，20字以内",
  "hook": "开头钩子，场景共鸣/痛点/好奇，3句话",
  "body": "正文，包含结构A/B/C/D之一，内容真实有说服力",
  "tags": ["精准长尾tag1", "长尾tag2", "使用场景tag3", "成分tag4", "平替tag5"],
  "cover_style": "封面图风格，要突出产品+情绪感",
  "image_styles": ["封面图prompt（产品+情绪风格）", "成分/对比图prompt", "使用场景图prompt"],
  "call_to_action": "结尾购买引导互动文案",
  "structure_type": "A/B/C/D 推荐使用的结构",
  "buy_guide": "挂链引导文案（不说具体品牌，说品类同款）",
  "tips": "发布建议：封面构图技巧、发布时间、评论区引导"
}""",
        "model": "gpt-image-2",
        "category_prompts": True
    },
    "微信公众号": {
        "system": """你是一位资深的新媒体编辑，擅长写阅读量10w+的公众号文章。

文案核心逻辑：
- 开头：画面感极强的场景描写，让读者"代入"
- 中间：层层递进，情绪共鸣，偶尔出金句让人想截图
- 结尾：开放式讨论或金句收尾，不矫情
- 节奏感：短句多，换行多，适合手机屏幕

风格底色：真诚、有洞察、不鸡汤、有态度

输出格式（严格按JSON返回，不要有任何其他内容）：
{
  "title": "标题，有共鸣或戳痛点，20字以内",
  "hook": "开头场景描写，制造代入感，2-3句话",
  "body": "正文，段落分明，每段不宜超过4行",
  "cover_style": "封面图风格描述",
  "image_styles": ["配图1描述", "配图2描述"],
  "summary": "文末金句或讨论话题",
  "tips": "发布建议"
}""",
        "model": "gpt-image-2"
    },
    "微博": {
        "system": """你是一位微博顶流博主，擅长写引发viral转发的短内容。

文案逻辑：
- 140字以内，一针见血
- 有态度、有情绪、有反转
- 悬念或金句是转发关键
- 配图提示单独标注

输出格式（严格按JSON返回，不要有任何其他内容）：
{
  "title": "微博话题标签或标题",
  "body": "正文，140字以内",
  "cover_style": "配图风格描述",
  "image_styles": [],
  "tips": "发布时机建议"
}""",
        "model": "gpt-image-2"
    }
}

# 品类专属爆款prompt
CATEGORY_PROMPTS = {
    "美妆护肤": {
        "focus": "成分党分析、肤感对比、使用前后对比、平替替代",
        "hot_structures": ["成分党型", "对比测评型", "使用感受型"],
        "keywords": ["成分", "肤感", "回购", "平替", "敏感肌", "油皮", "干皮", "熬夜党"]
    },
    "零食饮料": {
        "focus": "口感描述、场景代入、性价比、追剧零食、送礼场景",
        "hot_structures": ["使用感受型", "平替替代型"],
        "keywords": ["零食", "追剧", "宿舍", "办公室", "送礼", "回购", "零食分享", "热量"]
    },
    "家居好物": {
        "focus": "使用场景、收纳技巧、家居美学、租房改造、智能家居",
        "hot_structures": ["使用感受型", "对比测评型"],
        "keywords": ["收纳", "出租屋", "卧室", "客厅", "厨房", "好物分享", "家居美学", "小户型"]
    },
    "数码配件": {
        "focus": "性能对比、使用场景、平替替代、真实测评、性价比",
        "hot_structures": ["对比测评型", "成分党型"],
        "keywords": ["测评", "平替", "蓝牙耳机", "充电器", "数据线", "键盘", "鼠标", "续航"]
    },
    "服装穿搭": {
        "focus": "搭配技巧、场景穿搭、显瘦遮肉、平价替代、肤色搭配",
        "hot_structures": ["使用感受型", "对比测评型"],
        "keywords": ["穿搭", "显瘦", "小个子", "通勤", "约会", "平价", "搭配", "配色"]
    },
    "宠物用品": {
        "focus": "宠物使用感受、真实体验、性价比、安全性、多宠家庭",
        "hot_structures": ["使用感受型"],
        "keywords": ["猫粮", "狗粮", "宠物好物", "猫砂", "自动喂食器", "宠物零食", "多猫家庭"]
    },
    "母婴用品": {
        "focus": "安全性、成分、使用感受、性价比、宝宝阶段适配",
        "hot_structures": ["成分党型", "使用感受型"],
        "keywords": ["宝宝", "新生儿", "待产", "奶瓶", "纸尿裤", "婴儿推车", "辅食", "安全"]
    }
}


def call_llm(system_prompt, user_message):
    # Inject instruction to suppress thinking tags
    clean_system = system_prompt.strip()
    if not clean_system.endswith("不要输出思考过程，只输出最终答案。"):
        clean_system = "你是一个专业的内容创作助手。直接输出最终答案，不要输出任何思考过程、推理步骤或内心独白，只返回最终内容。\n\n" + clean_system

    payload = {
        "model": "MiniMax-M2.7",
        "messages": [
            {"role": "system", "content": clean_system},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.85,
        "max_tokens": 2500
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        MINIMAX_URL, data=data,
        headers={"Authorization": f"Bearer {MINIMAX_KEY}", "Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    raw_content = result["choices"][0]["message"]["content"]

    # Strip thinking tags if present
    content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()

    return content


def generate_image(prompt, output_path):
    payload = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "url"
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        IMG_URL, data=data,
        headers={"Authorization": f"Bearer {TOKLN_KEY}", "Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=240) as resp:
        result = json.loads(resp.read())

    image_url = result["data"][0]["url"]

    img_req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(img_req, timeout=60) as img_resp:
        img_data = img_resp.read()
        with open(output_path, "wb") as f:
            f.write(img_data)

    return output_path


# ──────────────────────────────────────────────
# 品类爆款分析
# ──────────────────────────────────────────────

@app.route("/analyze-category", methods=["POST"])
def analyze_category():
    """输入品类名，自动研究小红书爆款规律"""
    data = request.json
    category = data.get("category", "").strip()

    if not category:
        return jsonify({"error": "请输入品类"}), 400

    cat_info = CATEGORY_PROMPTS.get(category)

    system = f"""你是一位专注小红书内容数据分析的专家，研究过数千篇爆款种草笔记。

请分析「{category}」这个品类在小红书上的爆款规律，输出结构化分析报告。

分析维度：
1. 爆款内容结构（开头钩子、中段内容、结尾互动的常见模式）
2. 高点击率标题的规律（emoji使用、句式结构、关键词）
3. 爆款配图风格（色调、构图、人物/产品比例）
4. 爆款Tag组合规律
5. 最容易爆的内容类型（使用场景、人群定位、痛点切入）

输出格式（严格按JSON，不要有任何其他内容）：
{{
  "category": "{category}",
  "hot_patterns": ["规律1", "规律2", "规律3", "规律4", "规律5"],
  "title_rules": ["标题规律1", "标题规律2", "标题规律3"],
  "image_style": "配图整体风格描述",
  "tags_pattern": "Tag组合规律总结",
  "best_content_types": ["容易爆的内容类型1", "类型2", "类型3"],
  "avoid_mistakes": ["常见误区1", "误区2"],
  "recommend_structures": ["推荐内容结构A", "推荐结构B"],
  "posting_tips": "发布时机和运营建议"
}}"""

    try:
        result_text = call_llm(system, f"请分析「{category}」品类的爆款规律")

        # Try parsing JSON
        import json as _json
        result_text = result_text.strip()
        if result_text.startswith("```"):
            parts = result_text.split("```")
            for i, p in enumerate(parts):
                if p.strip().startswith("json"):
                    result_text = p[4:].strip()
                    break
                elif i % 2 == 1:
                    result_text = p.strip()
                    break

        result = _json.loads(result_text.strip())
        return jsonify(result)

    except _json.JSONDecodeError as e:
        return jsonify({"error": f"解析失败: {str(e)}\n原始内容:\n{result_text[:500]}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 爆款标题生成
# ──────────────────────────────────────────────

@app.route("/generate-titles", methods=["POST"])
def generate_titles():
    """针对品类生成多个高点击率标题备选"""
    data = request.json
    category = data.get("category", "").strip()
    product = data.get("product", "").strip()
    angle = data.get("angle", "").strip()  # 可选，角度切入

    if not category:
        return jsonify({"error": "请输入品类"}), 400

    cat_info = CATEGORY_PROMPTS.get(category, {})
    cat_keywords = cat_info.get("keywords", [])

    system = f"""你是一位小红书爆款标题专家，专门研究什么标题让人忍不住想点进去。

品类：{category}
{f"产品/品牌：{product}" if product else ""}
{f"切入角度：{angle}" if angle else ""}
关联关键词（参考）：{', '.join(cat_keywords)}

请生成10个不同风格的高点击率标题，要求：
- 每个标题≤20字
- 必须emoji开头
- 覆盖不同风格：好奇型/痛点型/共鸣型/反常识型/数字型
- 结合品类和产品的真实特点，不要标题党

输出格式（严格按JSON，不要有任何其他内容）：
{{
  "titles": [
    {{"text": "标题文字", "style": "好奇型", "reason": "为什么这个标题会火"}},
    ...共10个
  ]
}}"""

    try:
        prod_hint = ("，产品是" + product) if product else ""
        result_text = call_llm(system, f"请为{category}生成10个爆款标题" + prod_hint)

        import json as _json
        result_text = result_text.strip()
        if result_text.startswith("```"):
            parts = result_text.split("```")
            for i, p in enumerate(parts):
                if p.strip().startswith("json"):
                    result_text = p[4:].strip()
                    break
                elif i % 2 == 1:
                    result_text = p.strip()
                    break

        result = _json.loads(result_text.strip())
        return jsonify(result)

    except _json.JSONDecodeError as e:
        return jsonify({"error": f"解析失败: {str(e)}\n原始内容:\n{result_text[:500]}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 买手种草结构模板
# ──────────────────────────────────────────────

@app.route("/generate-template", methods=["POST"])
def generate_template():
    """生成买手种草模板（使用感受+成分分析+对比+推荐理由）"""
    data = request.json
    category = data.get("category", "").strip()
    product = data.get("product", "").strip()
    structure_type = data.get("structure", "").strip()  # A/B/C/D

    if not category:
        return jsonify({"error": "请输入品类"}), 400

    cat_info = CATEGORY_PROMPTS.get(category, {})
    cat_keywords = cat_info.get("keywords", [])

    system = f"""你是一位专业的小红书买手，擅长写高转化率的种草模板。

请为「{category}」{"产品："+product if product else ""}生成一套完整的买手种草模板，结构完整可以直接填入使用。

{f"指定结构类型：{structure_type}" if structure_type else "从4种结构中选最适合该品类的一种"}

结构选项：
- 结构A「成分党型」：成分解析 → 科学背书 → 真实使用感 → 推荐指数
- 结构B「对比测评型」：痛点导入 → 3款对比 → 优选推荐 → 购买引导
- 结构C「使用感受型」：场景共鸣 → 第一次用印象 → 持续使用变化 → 回购决定
- 结构D「平替替代型」：贵价痛点 → 找到平替 → 核心对比 → 省钱结论

关联关键词：{', '.join(cat_keywords)}

输出格式（严格按JSON，不要有任何其他内容）：
{{
  "structure_type": "推荐使用的结构（字母）",
  "structure_name": "结构名称",
  "title_template": "标题模板（{{}}是占位符可替换）",
  "hook_template": "开头钩子模板",
  "body_template": "正文完整模板（标注哪里填自己的真实感受）",
  "tags_suggested": ["推荐tag1", "tag2", "tag3", "tag4", "tag5"],
  "cover_prompt": "封面图风格prompt",
  "cta_template": "结尾CTA模板",
  "buy_guide_template": "挂链引导文案模板",
  "tips": "使用这个模板的注意事项"
}}"""

    try:
        prod_hint2 = ("，产品：" + product) if product else ""
        result_text = call_llm(system, f"请生成{category}的买手种草模板" + prod_hint2)

        import json as _json
        result_text = result_text.strip()
        if result_text.startswith("```"):
            parts = result_text.split("```")
            for i, p in enumerate(parts):
                if p.strip().startswith("json"):
                    result_text = p[4:].strip()
                    break
                elif i % 2 == 1:
                    result_text = p.strip()
                    break

        result = _json.loads(result_text.strip())
        return jsonify(result)

    except _json.JSONDecodeError as e:
        return jsonify({"error": f"解析失败: {str(e)}\n原始内容:\n{result_text[:500]}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 网页路由
# ──────────────────────────────────────────────

HTML = open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/generate", methods=["POST"])
def generate():
    """生成文案（支持参考图风格）"""
    data = request.json
    platform = data.get("platform", "小红书")
    request_text = data.get("request", "")
    extra_context = data.get("context", "")
    style_hint = data.get("style_hint", "")   # 从参考图提取的风格
    product_color = data.get("product_color", "")  # 参考图主色调

    if not request_text:
        return jsonify({"error": "请输入需求"}), 400

    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["小红书"])

    # 构建增强提示
    style_context = ""
    if style_hint:
        style_context += f"\n\n【参考图风格特征】{style_hint}"
    if product_color:
        style_context += f"\n【参考图主色调】{product_color}"

    user_msg = f"""需求：{request_text}
{f'背景信息：{extra_context}' if extra_context else ''}{style_context}

请严格按JSON格式输出，不要有任何其他内容。"""

    try:
        result_text = call_llm(template["system"], user_msg)

        json_str = result_text.strip()
        if json_str.startswith("```"):
            parts = json_str.split("```")
            for i, p in enumerate(parts):
                if p.strip().startswith("json"):
                    json_str = p[4:].strip()
                    break
                elif i % 2 == 1:
                    json_str = p.strip()
                    break
        json_str = json_str.strip()

        result = json.loads(json_str)

        # 如果有风格提示，加入到 image prompts
        if style_hint and "image_styles" in result:
            for i, style in enumerate(result["image_styles"]):
                result["image_styles"][i] = f"{style}, {style_hint}"

        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"AI返回格式有误，请重试: {str(e)}\n\n原始内容:\n{result_text[:500]}"}), 500
    except Exception as e:
        return jsonify({"error": f"生成失败: {str(e)}"}), 500


@app.route("/upload-reference", methods=["POST"])
def upload_reference():
    """上传参考图并分析风格"""
    if "image" not in request.files:
        return jsonify({"error": "没有上传图片"}), 400

    img_file = request.files["image"]
    img_data = img_file.read()

    # 分析风格
    style_info = analyze_image_style(img_data)

    # 保存原图
    ref_id = str(uuid.uuid4())[:8]
    ref_path = os.path.join(UPLOAD_DIR, f"ref_{ref_id}.png")
    with open(ref_path, "wb") as f:
        f.write(img_data)

    return jsonify({
        "ref_id": ref_id,
        "ref_url": f"/uploads/ref_{ref_id}.png",
        "style": style_info
    })


@app.route("/generate-images", methods=["POST"])
def generate_images():
    """生成图片"""
    data = request.json
    cover_prompt = data.get("cover_prompt", "")
    image_styles = data.get("image_styles", [])
    session_id = data.get("session_id", str(uuid.uuid4())[:8])
    style_hint = data.get("style_hint", "")
    ref_id = data.get("ref_id", "")  # 参考图ID

    results = {"session_id": session_id, "images": []}

    # 封面图
    if cover_prompt:
        final_cover_prompt = cover_prompt
        if style_hint:
            final_cover_prompt = f"{cover_prompt}, {style_hint}"
        try:
            cover_path = os.path.join(OUTPUT_DIR, f"{session_id}_cover.png")
            generate_image(final_cover_prompt, cover_path)
            results["images"].append({
                "type": "cover",
                "path": f"/output/{session_id}_cover.png",
                "prompt": final_cover_prompt
            })
        except Exception as e:
            results["images"].append({"type": "cover", "error": str(e)})

    # 配图
    for i, style in enumerate(image_styles[:4]):
        if not style:
            continue
        final_prompt = style
        if style_hint:
            final_prompt = f"{style}, {style_hint}"
        try:
            img_path = os.path.join(OUTPUT_DIR, f"{session_id}_img{i+1}.png")
            generate_image(final_prompt, img_path)
            results["images"].append({
                "type": "image",
                "index": i + 1,
                "path": f"/output/{session_id}_img{i+1}.png",
                "prompt": final_prompt
            })
        except Exception as e:
            results["images"].append({"type": "image", "index": i + 1, "error": str(e)})

    return jsonify(results)


@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    print("=" * 50)
    print("内容生成工具已启动")
    print("打开浏览器访问: http://localhost:5188")
    print("按 Ctrl+C 停止")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5188, debug=False)
