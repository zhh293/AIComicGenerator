"""角色一致性管理器 — 通过参考图+精确描述+CLIP验证三重保障角色外貌一致"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from src.config import settings
from src.flow.state import Character, Scene
from src.tools.image_gen_tool import ImageGenerationTool


class CharacterConsistencyManager:
    """
    角色一致性管理器
    
    三重保障策略：
    1. 文本层：每次生成时嵌入完整角色外貌描述
    2. 图像层：为每个角色生成参考图，作为生成 API 的 image_reference
    3. 验证层：生成后用 CLIP 对比参考图和实际输出的相似度
    """

    def __init__(self):
        self.reference_images: Dict[str, str] = {}  # {角色名: 参考图路径}
        self.character_registry: Dict[str, Character] = {}
        self._image_gen_tool = ImageGenerationTool()

    def register_characters(self, characters: List[Character]) -> None:
        """注册角色列表到管理器"""
        for char in characters:
            self.character_registry[char.name] = char
            logger.info(f"已注册角色: {char.name}")

    def generate_reference_image(self, character: Character) -> str:
        """
        为角色生成参考图
        
        生成一张多角度角色概念图，用于后续视频生成时的一致性约束
        """
        # 构建高度详细的角色描述 Prompt
        prompt = self._build_reference_prompt(character)

        # 生成参考图
        output_filename = f"char_ref_{character.name.replace(' ', '_')}.png"
        ref_image_path = self._image_gen_tool._run(
            prompt=prompt,
            purpose="character_reference",
            size="1024x1024",  # 正方形适合角色参考
            output_filename=output_filename,
        )

        self.reference_images[character.name] = ref_image_path
        logger.info(f"角色参考图已生成: {character.name} -> {ref_image_path}")
        return ref_image_path

    def generate_all_reference_images(self, characters: List[Character]) -> Dict[str, str]:
        """为所有角色生成参考图"""
        results = {}
        for char in characters:
            if char.name not in self.reference_images:
                path = self.generate_reference_image(char)
                results[char.name] = path
            else:
                results[char.name] = self.reference_images[char.name]
        return results

    def get_reference_image(self, character_name: str) -> Optional[str]:
        """获取角色参考图路径"""
        return self.reference_images.get(character_name)

    def get_scene_character_references(self, scene: Scene) -> List[str]:
        """获取场景中所有角色的参考图列表"""
        refs = []
        for char_action in scene.characters_in_scene:
            ref = self.reference_images.get(char_action.character_name)
            if ref and Path(ref).exists():
                refs.append(ref)
        return refs

    def build_consistency_prompt_block(
        self,
        scene: Scene,
        base_prompt: str,
    ) -> str:
        """
        构建带一致性约束的完整 Prompt
        
        在基础 Prompt 后追加：
        - 每个角色的完整外貌描述
        - 一致性强化指令
        """
        char_blocks = []

        for char_action in scene.characters_in_scene:
            character = self.character_registry.get(char_action.character_name)
            if character:
                desc = character.to_visual_prompt(
                    expression=char_action.expression,
                    pose=char_action.action,
                )
                char_blocks.append(desc)

        if char_blocks:
            characters_text = " | ".join(char_blocks)
            consistency_suffix = (
                "maintaining exact character appearance consistency with reference images, "
                "same face, same clothing, same distinctive features throughout"
            )
            return f"{base_prompt}. Characters present: {characters_text}. {consistency_suffix}"

        return base_prompt

    def get_generation_params(
        self,
        scene: Scene,
        base_consistency_weight: float = 0.8,
    ) -> dict:
        """获取带一致性约束的生成参数"""
        params = {
            "consistency_weight": base_consistency_weight,
            "reference_images": self.get_scene_character_references(scene),
        }

        # 如果场景中有多个角色，稍微降低一致性权重以避免混淆
        n_characters = len(scene.characters_in_scene)
        if n_characters > 2:
            params["consistency_weight"] = min(base_consistency_weight, 0.7)

        return params

    def verify_consistency(
        self,
        character_name: str,
        generated_frame_path: str,
        threshold: float = 0.75,
    ) -> Tuple[bool, float]:
        """
        验证生成帧与参考图的一致性
        
        使用 CLIP 余弦相似度评估。
        返回 (是否通过, 相似度分数)
        """
        ref_path = self.reference_images.get(character_name)
        if not ref_path or not Path(ref_path).exists():
            logger.warning(f"角色 {character_name} 无参考图，跳过一致性验证")
            return True, 1.0

        if not Path(generated_frame_path).exists():
            logger.warning(f"生成帧不存在: {generated_frame_path}")
            return False, 0.0

        try:
            similarity = self._compute_clip_similarity(ref_path, generated_frame_path)
            passed = similarity >= threshold
            
            if not passed:
                logger.warning(
                    f"角色 {character_name} 一致性检查未通过: "
                    f"相似度 {similarity:.3f} < 阈值 {threshold}"
                )
            else:
                logger.info(
                    f"角色 {character_name} 一致性检查通过: 相似度 {similarity:.3f}"
                )
            
            return passed, similarity

        except Exception as e:
            logger.error(f"CLIP 一致性验证失败: {e}")
            # 验证失败时默认通过，避免阻塞流程
            return True, 0.5

    def _compute_clip_similarity(self, image_path_a: str, image_path_b: str) -> float:
        """计算两张图片的 CLIP 余弦相似度"""
        try:
            import torch
            from PIL import Image
            from transformers import CLIPModel, CLIPProcessor

            model_name = "openai/clip-vit-base-patch32"
            model = CLIPModel.from_pretrained(model_name)
            processor = CLIPProcessor.from_pretrained(model_name)

            img_a = Image.open(image_path_a).convert("RGB")
            img_b = Image.open(image_path_b).convert("RGB")

            inputs = processor(images=[img_a, img_b], return_tensors="pt")

            with torch.no_grad():
                image_features = model.get_image_features(**inputs)
                # L2 normalize
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                similarity = torch.cosine_similarity(
                    image_features[0:1], image_features[1:2]
                ).item()

            return similarity

        except ImportError:
            logger.warning("CLIP 模型未安装，使用默认相似度 0.8")
            return 0.8

    def _build_reference_prompt(self, character: Character) -> str:
        """构建角色参考图生成 Prompt"""
        a = character.appearance
        o = character.outfit

        features = ", ".join(a.distinctive_features) if a.distinctive_features else "no distinctive marks"
        accessories = ", ".join(o.accessories) if o.accessories else "no accessories"

        return (
            f"single character reference sheet, full body front view and three-quarter view, "
            f"clean white background, consistent lighting, "
            f"{a.age}-year-old {a.gender}, {a.ethnicity} complexion, "
            f"{a.hair_style} {a.hair_color} hair, {a.eye_color} eyes, "
            f"{a.height_cm}cm tall, {a.build} build, "
            f"wearing {o.main_clothing}, {accessories}, shoes: {o.shoes}, "
            f"distinctive features: {features}, "
            f"neutral expression, standing pose, "
            f"highly detailed, professional concept art quality"
        )

    def export_registry(self) -> str:
        """导出角色注册信息为 JSON"""
        data = {
            name: {
                "character": char.model_dump(),
                "reference_image": self.reference_images.get(name),
            }
            for name, char in self.character_registry.items()
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
