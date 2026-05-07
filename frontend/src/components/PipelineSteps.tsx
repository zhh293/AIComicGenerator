import { Steps } from 'antd';
import {
  RocketOutlined,
  EditOutlined,
  SafetyCertificateOutlined,
  PictureOutlined,
  VideoCameraOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { StageProgress } from '../api/types';

const stageConfig: Record<string, { title: string; icon: React.ReactNode }> = {
  initialization: { title: '初始化', icon: <RocketOutlined /> },
  screenplay_creation: { title: '剧本创作', icon: <EditOutlined /> },
  screenplay_quality_check: { title: '剧本质检', icon: <SafetyCertificateOutlined /> },
  asset_generation: { title: '素材生成', icon: <PictureOutlined /> },
  asset_quality_check: { title: '素材质检', icon: <SafetyCertificateOutlined /> },
  video_composition: { title: '视频合成', icon: <VideoCameraOutlined /> },
  final_quality_check: { title: '最终质检', icon: <CheckCircleOutlined /> },
};

function mapStatus(status: string): 'wait' | 'process' | 'finish' | 'error' {
  switch (status) {
    case 'completed': return 'finish';
    case 'running': return 'process';
    case 'failed': return 'error';
    default: return 'wait';
  }
}

interface Props {
  stages: StageProgress[];
}

export default function PipelineSteps({ stages }: Props) {
  if (!stages || stages.length === 0) {
    return <div className="text-slate-400 text-center py-4">流水线尚未启动</div>;
  }

  const items = stages.map((stage) => {
    const config = stageConfig[stage.stage_name] || { title: stage.stage_name, icon: null };
    return {
      title: config.title,
      icon: config.icon,
      status: mapStatus(stage.status),
      description: stage.score != null ? `评分: ${stage.score.toFixed(1)}` : (stage.message || undefined),
    };
  });

  return (
    <Steps
      items={items}
      size="small"
      className="!my-4"
      responsive
    />
  );
}
