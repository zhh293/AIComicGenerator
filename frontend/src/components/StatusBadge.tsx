import { Tag } from 'antd';
import {
  ClockCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { ProjectStatus } from '../api/types';

const statusConfig: Record<ProjectStatus, { color: string; icon: React.ReactNode; label: string }> = {
  [ProjectStatus.QUEUED]: { color: 'default', icon: <ClockCircleOutlined />, label: '排队中' },
  [ProjectStatus.RUNNING]: { color: 'processing', icon: <SyncOutlined spin />, label: '生产中' },
  [ProjectStatus.AWAITING_APPROVAL]: { color: 'warning', icon: <ExclamationCircleOutlined />, label: '待审批' },
  [ProjectStatus.COMPLETED]: { color: 'success', icon: <CheckCircleOutlined />, label: '已完成' },
  [ProjectStatus.FAILED]: { color: 'error', icon: <CloseCircleOutlined />, label: '失败' },
  [ProjectStatus.CANCELLED]: { color: 'default', icon: <StopOutlined />, label: '已取消' },
};

interface Props {
  status: ProjectStatus;
  size?: 'small' | 'default';
}

export default function StatusBadge({ status, size = 'default' }: Props) {
  const config = statusConfig[status] || statusConfig[ProjectStatus.QUEUED];
  return (
    <Tag
      color={config.color}
      icon={config.icon}
      className={size === 'small' ? '!text-xs' : ''}
    >
      {config.label}
    </Tag>
  );
}
