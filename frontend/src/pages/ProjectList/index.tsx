import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Input, Segmented, Progress, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../../api/projects';
import StatusBadge from '../../components/StatusBadge';
import { ProjectStatus, type ProjectBrief } from '../../api/types';
import dayjs from 'dayjs';

const statusTabs = [
  { label: '全部', value: '' },
  { label: '进行中', value: ProjectStatus.RUNNING },
  { label: '待审批', value: ProjectStatus.AWAITING_APPROVAL },
  { label: '已完成', value: ProjectStatus.COMPLETED },
  { label: '失败', value: ProjectStatus.FAILED },
];

export default function ProjectList() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['projects', page, statusFilter],
    queryFn: () =>
      projectApi.list({
        page,
        page_size: 20,
        status: statusFilter || undefined,
      }),
    refetchInterval: (query) => {
      const projects = query.state.data?.projects;
      const hasRunning = projects?.some(
        (p) => p.status === ProjectStatus.RUNNING || p.status === ProjectStatus.QUEUED,
      );
      return hasRunning ? 5000 : false;
    },
  });

  const filteredProjects = (data?.projects ?? []).filter((p) => {
    if (!search) return true;
    return (
      p.title?.toLowerCase().includes(search.toLowerCase()) ||
      p.project_id.includes(search)
    );
  });

  const columns = [
    {
      title: '项目',
      key: 'title',
      render: (_: unknown, record: ProjectBrief) => (
        <div>
          <div className="font-medium text-slate-700">
            {record.title || `项目 ${record.project_id.slice(0, 8)}`}
          </div>
          <div className="text-xs text-slate-400 mt-0.5">{record.project_id}</div>
        </div>
      ),
    },
    {
      title: '风格',
      dataIndex: 'style',
      key: 'style',
      render: (style: string) => (
        <span className="px-2 py-0.5 bg-slate-100 rounded text-xs text-slate-600">{style}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: ProjectStatus) => <StatusBadge status={status} />,
    },
    {
      title: '进度',
      dataIndex: 'progress_percent',
      key: 'progress',
      render: (percent: number) => (
        <Progress
          percent={Math.round(percent)}
          size="small"
          strokeColor={{ '0%': '#6366f1', '100%': '#a855f7' }}
        />
      ),
    },
    {
      title: '时长',
      dataIndex: 'duration',
      key: 'duration',
      render: (d: number) => `${d}s`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => dayjs(t).format('MM-DD HH:mm'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-slate-800">项目列表</h2>
        <Input
          placeholder="搜索项目..."
          prefix={<SearchOutlined className="text-slate-400" />}
          className="!w-64 !rounded-lg"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          allowClear
        />
      </div>

      <Card className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <Segmented
          options={statusTabs}
          value={statusFilter}
          onChange={(val) => {
            setStatusFilter(val as string);
            setPage(1);
          }}
          className="mb-6"
        />

        {filteredProjects.length === 0 && !isLoading ? (
          <Empty description="暂无项目" />
        ) : (
          <Table
            dataSource={filteredProjects}
            columns={columns}
            rowKey="project_id"
            loading={isLoading}
            onRow={(record) => ({
              onClick: () => navigate(`/projects/${record.project_id}`),
              className: 'cursor-pointer hover:bg-slate-50/80 transition-colors',
            })}
            pagination={{
              current: page,
              total: data?.total ?? 0,
              pageSize: 20,
              onChange: setPage,
              showSizeChanger: false,
            }}
          />
        )}
      </Card>
    </div>
  );
}
