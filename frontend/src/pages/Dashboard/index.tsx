import { useQuery } from '@tanstack/react-query';
import { Card, Statistic, Button, List, Progress, Skeleton } from 'antd';
import {
  PlusOutlined,
  ThunderboltOutlined,
  CloudServerOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../../api/projects';
import StatusBadge from '../../components/StatusBadge';
import type { ProjectBrief } from '../../api/types';

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: projectApi.health,
    refetchInterval: 10000,
  });

  const { data: recentProjects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects', 'recent'],
    queryFn: () => projectApi.list({ page: 1, page_size: 5 }),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-8">
      {/* Hero区域 */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 p-8 md:p-12 text-white">
        <div className="relative z-10">
          <h1 className="text-3xl md:text-4xl font-bold mb-3">AI Film Studio</h1>
          <p className="text-white/80 text-lg mb-6 max-w-xl">
            多 Agent 协作的 AI 短剧自动生成平台，从创意到成片一键完成
          </p>
          <Button
            type="primary"
            size="large"
            icon={<PlusOutlined />}
            onClick={() => navigate('/create')}
            className="!bg-white !text-indigo-600 !border-none hover:!bg-white/90 !font-semibold !h-12 !px-8 !rounded-lg"
          >
            开始创作
          </Button>
        </div>
        {/* 背景装饰 */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-1/3 w-48 h-48 bg-white/5 rounded-full translate-y-1/2" />
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="hover-card !rounded-xl !border-slate-200/60 !shadow-sm">
          <Skeleton loading={healthLoading} active paragraph={false}>
            <Statistic
              title={<span className="text-slate-500">活跃项目</span>}
              value={health?.active_projects ?? 0}
              prefix={<ThunderboltOutlined className="text-indigo-500" />}
            />
          </Skeleton>
        </Card>
        <Card className="hover-card !rounded-xl !border-slate-200/60 !shadow-sm">
          <Skeleton loading={healthLoading} active paragraph={false}>
            <Statistic
              title={<span className="text-slate-500">队列等待</span>}
              value={health?.queue_size ?? 0}
              prefix={<CloudServerOutlined className="text-orange-500" />}
            />
          </Skeleton>
        </Card>
        <Card className="hover-card !rounded-xl !border-slate-200/60 !shadow-sm">
          <Skeleton loading={healthLoading} active paragraph={false}>
            <Statistic
              title={<span className="text-slate-500">服务版本</span>}
              value={health?.version ?? '-'}
              prefix={<AppstoreOutlined className="text-green-500" />}
            />
          </Skeleton>
        </Card>
      </div>

      {/* 最近项目 */}
      <Card
        title={<span className="font-semibold text-slate-700">最近项目</span>}
        extra={
          <Button type="link" onClick={() => navigate('/projects')}>
            查看全部
          </Button>
        }
        className="!rounded-xl !border-slate-200/60 !shadow-sm"
      >
        <List
          loading={projectsLoading}
          dataSource={recentProjects?.projects ?? []}
          locale={{ emptyText: '暂无项目，点击上方按钮开始创作' }}
          renderItem={(item: ProjectBrief) => (
            <List.Item
              className="cursor-pointer hover:bg-slate-50/80 !px-4 !rounded-lg transition-colors"
              onClick={() => navigate(`/projects/${item.project_id}`)}
              extra={
                <Progress
                  type="circle"
                  percent={Math.round(item.progress_percent)}
                  size={44}
                  strokeColor={{ '0%': '#6366f1', '100%': '#a855f7' }}
                />
              }
            >
              <List.Item.Meta
                title={
                  <span className="font-medium text-slate-700">
                    {item.title || `项目 ${item.project_id.slice(0, 8)}`}
                  </span>
                }
                description={
                  <div className="flex items-center gap-3 mt-1">
                    <StatusBadge status={item.status} size="small" />
                    <span className="text-xs text-slate-400">
                      {item.style} · {item.duration}s
                    </span>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
