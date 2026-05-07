import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Button, Descriptions, Spin, Result as AntResult } from 'antd';
import { DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { projectApi } from '../../api/projects';
import { ProjectStatus } from '../../api/types';
import EmotionChart from '../../components/EmotionChart';
import dayjs from 'dayjs';

export default function Result() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectApi.getDetail(id!),
    enabled: !!id,
  });

  const { data: downloadInfo } = useQuery({
    queryKey: ['download', id],
    queryFn: () => projectApi.getDownload(id!),
    enabled: !!id && project?.status === ProjectStatus.COMPLETED,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  if (!project || project.status !== ProjectStatus.COMPLETED) {
    return (
      <AntResult
        status="info"
        title="成片尚未就绪"
        subTitle="项目尚未完成，请等待生产流程结束"
        extra={
          <Button onClick={() => navigate(`/projects/${id}`)}>
            返回详情
          </Button>
        }
      />
    );
  }

  // 模拟情绪数据
  const emotionData = Array.from({ length: 6 }, (_, i) => ({
    scene_id: i + 1,
    tension: Math.random() * 0.7 + 0.2,
    valence: Math.random() * 0.8 + 0.1,
    energy: Math.random() * 0.6 + 0.3,
    mood_label: ['序幕', '铺垫', '发展', '高潮', '转折', '结局'][i],
  }));

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(`/projects/${id}`)}
        className="!text-slate-500"
      >
        返回详情
      </Button>

      {/* 视频播放器 */}
      <Card className="!rounded-xl !border-slate-200/60 !shadow-sm overflow-hidden">
        <div className="bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center">
          {downloadInfo?.video_url ? (
            <video
              controls
              className="w-full h-full"
              src={downloadInfo.video_url}
              poster=""
            >
              您的浏览器不支持视频播放
            </video>
          ) : (
            <div className="text-white/50 text-center">
              <p className="text-lg">视频加载中...</p>
              <p className="text-sm mt-2">视频文件准备就绪后将在此播放</p>
            </div>
          )}
        </div>

        <div className="flex justify-between items-center mt-6">
          <h2 className="text-xl font-bold text-slate-800">
            {project.title || '未命名短剧'}
          </h2>
          {downloadInfo?.video_url && (
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              href={downloadInfo.video_url}
              className="!rounded-lg"
            >
              下载成片
            </Button>
          )}
        </div>
      </Card>

      {/* 项目信息 */}
      <Card title="项目信息" className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="风格">{project.style}</Descriptions.Item>
          <Descriptions.Item label="时长">{project.duration}s</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {dayjs(project.created_at).format('YYYY-MM-DD HH:mm:ss')}
          </Descriptions.Item>
          <Descriptions.Item label="质量评分">
            {Object.entries(project.quality_scores)
              .filter(([, v]) => v != null)
              .map(([k, v]) => `${k}: ${v!.toFixed(1)}`)
              .join(' · ') || '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 情绪曲线回顾 */}
      <Card title="情绪曲线" className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <EmotionChart data={emotionData} height={280} />
      </Card>
    </div>
  );
}
