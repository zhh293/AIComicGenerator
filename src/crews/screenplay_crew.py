"""剧本创作 Crew — 从用户描述生成完整结构化剧本"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from src.config import settings
from src.flow.state import Character, Screenplay, StyleType
from src.llm import get_llm
from src.style.presets import StylePresetConfig


class ScreenplayCrew:
    """
    剧本创作 Crew
    
    包含三个 Agent：
    1. 故事架构师 — 构建故事框架（三幕结构、情感弧线）
    2. 分镜编剧 — 将故事拆解为可视化场景序列
    3. 角色设计师 — 创建精确的角色视觉档案
    
    最终输出结构化的 Screenplay 对象
    """

    def __init__(
        self,
        style_config: StylePresetConfig,
        target_duration: float = 60.0,
        style_type: StyleType = StyleType.CINEMATIC,
    ):
        self.style_config = style_config
        self.target_duration = target_duration
        self.style_type = style_type
        self._llm = get_llm()

    def crew(self) -> Crew:
        """组装并返回 Crew 实例"""
        return Crew(
            agents=[
                self._story_architect(),
                self._scene_writer(),
                self._character_designer(),
            ],
            tasks=[
                self._story_framework_task(),
                self._scene_breakdown_task(),
                self._character_profile_task(),
                self._final_assembly_task(),
            ],
            process=Process.sequential,
            verbose=True,
        )

    # ================================================================
    # Agent 定义
    # ================================================================

    def _story_architect(self) -> Agent:
        return Agent(
            role="故事架构师 (Story Architect)",
            goal=(
                "根据用户描述构建完整的故事框架，包含三幕结构、核心冲突、"
                "情感弧线和主题思想。确保故事在给定时长内有完整的起承转合。"
            ),
            backstory=(
                "你是一位获得过多项编剧大奖的资深故事架构师。"
                "你精通三幕式结构、英雄旅程、情感曲线等经典叙事技巧，"
                "同时擅长用极简的设定构建打动人心的短故事。"
                "你深知短片的精髓在于'一个核心情感 + 一个关键转折'，"
                "不贪多不冗长，每一个情节都服务于主题。"
            ),
            llm=self._llm,
            verbose=True,
        )

    def _scene_writer(self) -> Agent:
        return Agent(
            role="分镜编剧 (Visual Scene Writer)",
            goal=(
                "将故事框架拆解为具体的、可直接用于 AI 视频生成的场景序列。"
                "每个场景都有精确的画面描述、镜头运动和光照设定。"
            ),
            backstory=(
                "你是一位视觉化思维极强的编剧兼分镜师，曾为多部视效大片做分镜。"
                "你的独特能力是把抽象的叙事转化为具体的画面语言。"
                "你精通电影镜头语言——景别、运镜、构图、光线、色彩都是你的表达工具。"
                f"你深度理解{self.style_config.display_name}风格的视觉特点，"
                "能够自然融入该风格的美学元素。"
                "你写出的场景描述要足够具体，让 AI 图片/视频生成模型能直接理解。"
            ),
            llm=self._llm,
            verbose=True,
        )

    def _character_designer(self) -> Agent:
        return Agent(
            role="角色视觉设计师 (Character Visual Designer)",
            goal=(
                "为每个角色创建极其精确、一致的视觉描述档案。"
                "这些描述将直接用于 AI 生成，必须精确到可以在不同场景中"
                "保持角色外貌完全一致。"
            ),
            backstory=(
                "你是顶尖的角色概念设计师，曾服务于迪士尼和皮克斯。"
                "你最擅长的是用文字精确描述角色外貌——精确到色号、比例、纹理。"
                "你深知'一致性'的重要性：同一角色在任何场景下都必须看起来一样。"
                "你的描述风格：具体量化（不用'较高'而用'178cm'），"
                "用色彩代码（不用'浅棕色'而用'warm brown #8B6914'），"
                "明确形状（不用'大眼睛'而用'almond-shaped eyes with double eyelids'）。"
            ),
            llm=self._llm,
            verbose=True,
        )

    # ================================================================
    # Task 定义
    # ================================================================

    def _story_framework_task(self) -> Task:
        return Task(
            description=(
                "基于以下用户输入，构建完整的故事框架：\n\n"
                "用户描述：{user_prompt}\n"
                f"目标时长：{self.target_duration} 秒\n"
                f"风格类型：{self.style_config.display_name}\n\n"
                "要求：\n"
                "1. 确定明确的核心主题和情感基调\n"
                "2. 设计三幕结构：\n"
                "   - 第一幕（建置 25%）：介绍世界观、主角、日常状态\n"
                "   - 第二幕（对抗 50%）：核心冲突升级、挑战与挣扎\n"
                "   - 第三幕（解决 25%）：高潮、转折、情感释放/升华\n"
                "3. 确定主要角色（2-4个为佳）\n"
                "4. 明确每一幕的核心事件和情感转折点\n"
                "5. 设计一句话概述（logline）\n\n"
                "注意：这是短片，不是长篇电影。每一个情节必须精炼有力。"
            ),
            expected_output=(
                "包含 title, logline, synopsis, theme, tone, 三幕结构描述, "
                "角色名单及简介的完整故事框架文档"
            ),
            agent=self._story_architect(),
        )

    def _scene_breakdown_task(self) -> Task:
        return Task(
            description=(
                "基于故事框架，将故事拆解为具体的视觉场景序列。\n\n"
                f"目标总时长: {self.target_duration} 秒\n"
                f"视觉风格: {self.style_config.display_name}\n"
                f"风格特征: {self.style_config.description}\n\n"
                "对每个场景，必须提供：\n"
                "1. 场景地点和环境描述（具体到光线、色调、氛围）\n"
                "2. 出场角色和其在该场景中的动作\n"
                "3. 镜头景别（wide/medium/close-up 等）\n"
                "4. 镜头运动（static/pan/dolly/tracking 等）\n"
                "5. 时间段（day/night/golden_hour 等）\n"
                "6. 情绪基调\n"
                "7. 对话或旁白（如有）\n"
                "8. 场景时长（5-15秒）\n"
                "9. 到下一场景的转场方式\n\n"
                "关键原则：\n"
                "- 所有场景时长之和必须接近目标时长\n"
                "- 开场用宽镜头建立环境感\n"
                "- 情感高潮时用特写强化情绪\n"
                "- 转场要有节奏感，不要每个都相同\n"
                f"- 风格偏好的转场类型: {self.style_config.preferred_transitions}"
            ),
            expected_output=(
                "按时间顺序排列的完整场景序列，每个场景包含以上所有必填信息"
            ),
            agent=self._scene_writer(),
        )

    def _character_profile_task(self) -> Task:
        return Task(
            description=(
                "为故事中的每个角色创建详细的视觉档案。\n\n"
                "这些档案将直接用于 AI 图片/视频生成，必须足够精确以保证\n"
                "同一角色在所有场景中的外貌完全一致。\n\n"
                "对每个角色，必须明确指定：\n\n"
                "【外貌】\n"
                "- 年龄（精确数字）\n"
                "- 性别\n"
                "- 肤色（用英文描述 + HEX 色号，如 'fair East Asian #F5DEB3'）\n"
                "- 身高（厘米）和体型（slender/athletic/average/stocky）\n"
                "- 发型（具体描述长度、卷直、刘海等）和发色\n"
                "- 瞳色\n"
                "- 标志性特征（痣、疤痕、纹身等明确辨识物）\n\n"
                "【服装】\n"
                "- 主要服装（详细描述款式、材质、颜色）\n"
                "- 配饰（首饰、眼镜、包等）\n"
                "- 鞋子\n"
                "- 服装主色调列表\n\n"
                "【性格与声音】\n"
                "- 性格特征概述\n"
                "- 音色描述（供 TTS 参考，如'低沉温暖的男中音'）\n\n"
                "重要提醒：\n"
                "- 不要用模糊词如'好看的'、'普通的'，必须具体量化\n"
                "- 不要用'大约'、'差不多'，给出精确值\n"
                "- 颜色必须附带英文色名"
            ),
            expected_output="每个角色的完整视觉档案，格式化为可直接解析的结构化描述",
            agent=self._character_designer(),
        )

    def _final_assembly_task(self) -> Task:
        return Task(
            description=(
                "将故事框架、场景序列和角色档案整合为完整的结构化剧本。\n\n"
                "核心任务：为每个场景生成可直接用于 AI 视频生成的 visual_prompt。\n\n"
                "visual_prompt 编写规则：\n"
                "1. 必须用英文\n"
                "2. 结构: [风格描述], [环境], [角色外貌+动作], [光线], [镜头], [氛围]\n"
                f"3. 融入风格前缀关键词: {self.style_config.visual_prefix[:100]}...\n"
                "4. 引用角色档案中的精确外貌描述（不能简化）\n"
                "5. 每个 prompt 长度在 150-300 词之间\n\n"
                "同时确保：\n"
                "- 所有场景编号连续且无遗漏\n"
                "- 总时长与目标时长偏差不超过 10%\n"
                "- 每个场景至少有 environment_description 和 visual_prompt\n"
                "- 角色列表完整且与场景中引用的角色一致\n\n"
                "最终输出必须严格符合 Screenplay 数据模型结构。"
            ),
            expected_output=(
                "完整的 Screenplay 对象，包含 title, logline, synopsis, theme, tone, "
                "acts, scenes（带 visual_prompt）, characters 所有字段"
            ),
            agent=self._scene_writer(),
            output_pydantic=Screenplay,
        )
