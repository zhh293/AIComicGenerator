import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface EmotionPoint {
  scene_id: number;
  tension: number;
  valence: number;
  energy: number;
  mood_label?: string;
}

interface Props {
  data: EmotionPoint[];
  height?: number;
}

export default function EmotionChart({ data, height = 300 }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-400">
        暂无情绪曲线数据
      </div>
    );
  }

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const items = params as Array<{ seriesName: string; value: number; dataIndex: number }>;
        const idx = items[0]?.dataIndex ?? 0;
        const point = data[idx];
        let html = `<div class="font-medium">场景 ${point.scene_id}</div>`;
        if (point.mood_label) {
          html += `<div class="text-xs text-gray-500">${point.mood_label}</div>`;
        }
        items.forEach((item) => {
          html += `<div>${item.seriesName}: ${item.value.toFixed(2)}</div>`;
        });
        return html;
      },
    },
    legend: {
      data: ['张力', '情感极性', '能量'],
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: data.map((p) => `S${p.scene_id}`),
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: '张力',
        type: 'line',
        data: data.map((p) => p.tension),
        smooth: true,
        lineStyle: { color: '#ef4444', width: 2 },
        itemStyle: { color: '#ef4444' },
        areaStyle: { color: 'rgba(239, 68, 68, 0.05)' },
      },
      {
        name: '情感极性',
        type: 'line',
        data: data.map((p) => p.valence),
        smooth: true,
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
        areaStyle: { color: 'rgba(59, 130, 246, 0.05)' },
      },
      {
        name: '能量',
        type: 'line',
        data: data.map((p) => p.energy),
        smooth: true,
        lineStyle: { color: '#f97316', width: 2 },
        itemStyle: { color: '#f97316' },
        areaStyle: { color: 'rgba(249, 115, 22, 0.05)' },
      },
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}
