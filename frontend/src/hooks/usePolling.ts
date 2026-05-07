import { ProjectStatus } from '../api/types';

/**
 * 根据项目状态返回轮询间隔（毫秒）
 * 终态返回 false 停止轮询
 */
export function getPollingInterval(status?: ProjectStatus): number | false {
  switch (status) {
    case ProjectStatus.QUEUED:
      return 5000;
    case ProjectStatus.RUNNING:
      return 3000;
    case ProjectStatus.AWAITING_APPROVAL:
      return 10000;
    default:
      return false;
  }
}
