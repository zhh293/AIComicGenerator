import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Button,
  Progress,
  Tabs,
  Modal,
  Input,
  message,
  Descriptions,
  Spin,
  Result,
  Space,
} from 'antd';
import {
  CheckOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import { projectApi } from '../../api/projects';
import { ProjectStatus } from '../../api/types';
import StatusBadge from '../../components/StatusBadge';
import PipelineSteps from '../../components/PipelineSteps';
import EmotionChart from '../../components/EmotionChart';
import { getPollingInterval } from '../../hooks/usePolling';
import dayjs from 'dayjs';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [retryModal, setRetryModal] = useState(false);
  const [feedback, setFeedback] = useState('');

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectApi.getDetail(id!),
    enabled: !!id,
    refetchInterval: (query) => getPollingInterval(query.state.data?.status),
  });

  const approveMutation = useMutation({
    mutationFn: () => projectApi.approve(id!),
    onSuccess: () => {
      message.success('剧本已通过审批，继续生产');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => projectApi.cancel(id!),
    onSuccess: () => {
      message.success('项目已取消');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: (stage: string) => projectApi.retry(id!, stage, feedback || undefined),
    onSuccess: () => {
      message.success('重试已发起');
      setRetryModal(false);
      setFeedback('');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return <Result status="404" title="项目不存在" subTitle="请检查项目 ID 是否正确" />;
  }

  // 模拟情绪曲线数据（来自 quality_scores 或后续接口）
  const mockEmotionData = project.stages
    .filter((s) => s.status === 'completed')
    .map((_, i) => ({
      scene_id: i + 1,
      tension: Math.random() * 0.7 + 0.2,
      valence: Math.random() * 0.8 + 0.1,
      energy: Math.random() * 0.6 + 0.3,
      mood_label: ['平静', '紧张', '高潮', '舒缓', '震撼', '温情', '结局'][i % 7],
    }));

  const terminalStatuses: string[] = [ProjectStatus.COMPLETED, ProjectStatus.FAILED, ProjectStatus.CANCELLED];
  const isTerminal = terminalStatuses.includes(project.status);

  return (
    <div className="space-y-6">
      {/* 顶部信息 */}
      <Card className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">
              {project.title || `项目 ${project.project_id.slice(0, 8)}`}
            </h2>
            <div className="flex items-center gap-4">
              <StatusBadge status={project.status} />
              <span className="text-sm text-slate-500">{project.style}</span>
              <span className="text-sm text-slate-500">{project.duration}s</span>
              <span className="text-sm text-slate-400">
                {dayjs(project.created_at).format('YYYY-MM-DD HH:mm')}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Progress
              type="dashboard"
              percent={Math.round(
                project.stages.filter((s) => s.status === 'completed').length /
                  Math.max(project.stages.length, 1) * 100,
              )}
              size={80}
              strokeColor={{ '0%': '#6366f1', '100%': '#a855f7' }}
            />
          </div>
        </div>
      </Card>

      {/* 操作按钮区 */}
      {project.status === ProjectStatus.AWAITING_APPROVAL && (
        <Card className="!rounded-xl !border-orange-200 !bg-orange-50/50 !shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-orange-800">剧本待审批</h3>
              <p className="text-sm text-orange-600 mt-1">剧本已生成完毕，请审核后决定是否继续生产</p>
            </div>
            <Space>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                onClick={() => approveMutation.mutate()}
                loading={approveMutation.isPending}
              >
                通过
              </Button>
              <Button
                danger
                icon={<ReloadOutlined />}
                onClick={() => setRetryModal(true)}
              >
                打回重做
              </Button>
            </Space>
          </div>
        </Card>
      )}

      {project.status === ProjectStatus.COMPLETED && (
        <Card className="!rounded-xl !border-green-200 !bg-green-50/50 !shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-green-800">制作完成</h3>
              <p className="text-sm text-green-600 mt-1">短剧已生成，可以预览和下载</p>
            </div>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => navigate(`/projects/${id}/result`)}
              className="!bg-green-600 !border-green-600 hover:!bg-green-700"
            >
              查看成片
            </Button>
          </div>
        </Card>
      )}

      {/* 流水线进度 */}
      <Card title="生产流水线" className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <PipelineSteps stages={project.stages} />
      </Card>

      {/* 详情 Tabs */}
      <Card className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <Tabs
          items={[
            {
              key: 'screenplay',
              label: '剧本概要',
              children: (
                <div className="prose prose-slate max-w-none">
                  {project.screenplay_summary ? (
                    <div className="whitespace-pre-wrap text-slate-600 leading-relaxed p-4 bg-slate-50 rounded-lg">
                      {project.screenplay_summary}
                    </div>
                  ) : (
                    <p className="text-slate-400 text-center py-8">剧本尚未生成</p>
                  )}
                </div>
              ),
            },
            {
              key: 'emotion',
              label: '情绪曲线',
              children: <EmotionChart data={mockEmotionData} height={320} />,
            },
            {
              key: 'quality',
              label: '质量报告',
              children: (
                <Descriptions column={2} bordered size="small">
                  {Object.entries(project.quality_scores).map(([key, val]) => (
                    <Descriptions.Item key={key} label={key}>
                      {val != null ? (
                        <span className={val >= 7 ? 'text-green-600 font-semibold' : 'text-orange-600'}>
                          {val.toFixed(1)} / 10
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              ),
            },
            ...(project.error
              ? [{
                  key: 'error',
                  label: '错误日志',
                  children: (
                    <div className="p-4 bg-red-50 rounded-lg text-red-700 text-sm font-mono whitespace-pre-wrap">
                      {project.error}
                    </div>
                  ),
                }]
              : []),
          ]}
        />
      </Card>

      {/* 底部操作 */}
      {!isTerminal && (
        <div className="flex justify-end gap-3">
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              Modal.confirm({
                title: '确认取消',
                content: '取消后将停止当前生产流程，确认继续？',
                onOk: () => cancelMutation.mutate(),
              });
            }}
          >
            取消项目
          </Button>
        </div>
      )}

      {project.status === ProjectStatus.FAILED && (
        <div className="flex justify-end">
          <Button
            icon={<ReloadOutlined />}
            onClick={() => setRetryModal(true)}
          >
            重试
          </Button>
        </div>
      )}

      {/* 重试 Modal */}
      <Modal
        title="重试阶段"
        open={retryModal}
        onCancel={() => setRetryModal(false)}
        onOk={() => {
          const failedStage = project.stages.find((s) => s.status === 'failed');
          retryMutation.mutate(failedStage?.stage_name || 'screenplay');
        }}
        confirmLoading={retryMutation.isPending}
      >
        <p className="text-slate-600 mb-4">
          将重试失败的阶段，你可以附加修改建议：
        </p>
        <Input.TextArea
          rows={3}
          placeholder="可选：输入修改建议或反馈..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
        />
      </Modal>
    </div>
  );
}
