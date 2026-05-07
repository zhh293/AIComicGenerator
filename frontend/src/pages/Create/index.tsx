import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Card,
  Form,
  Input,
  Slider,
  Switch,
  Radio,
  Button,
  message,
  Spin,
} from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { projectApi } from '../../api/projects';
import type { CreateProjectRequest, StyleInfo } from '../../api/types';

const { TextArea } = Input;

// 风格封面配色（渐变占位）
const styleGradients: Record<string, string> = {
  cinematic: 'from-amber-500 to-orange-600',
  anime: 'from-pink-400 to-rose-500',
  cyberpunk: 'from-cyan-500 to-blue-600',
  ink_wash: 'from-slate-400 to-stone-600',
  realistic: 'from-emerald-500 to-teal-600',
};

export default function Create() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [selectedStyle, setSelectedStyle] = useState('cinematic');

  const { data: styles, isLoading: stylesLoading } = useQuery({
    queryKey: ['styles'],
    queryFn: projectApi.getStyles,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateProjectRequest) => projectApi.create(data),
    onSuccess: (resp) => {
      message.success('项目创建成功！');
      navigate(`/projects/${resp.project_id}`);
    },
  });

  const onFinish = (values: Record<string, unknown>) => {
    const payload: CreateProjectRequest = {
      prompt: values.prompt as string,
      style: selectedStyle as CreateProjectRequest['style'],
      duration: values.duration as number,
      title: (values.title as string) || undefined,
      language: values.language as string,
      auto_approve: values.auto_approve as boolean,
    };
    createMutation.mutate(payload);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="mb-2">
        <h2 className="text-2xl font-bold text-slate-800">创建新项目</h2>
        <p className="text-slate-500 mt-1">描述你的故事创意，AI 将自动完成从剧本到成片的全流程</p>
      </div>

      {/* 风格选择器 */}
      <Card title="选择视觉风格" className="!rounded-xl !border-slate-200/60 !shadow-sm">
        {stylesLoading ? (
          <div className="flex justify-center py-8"><Spin /></div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {(styles ?? []).map((style: StyleInfo) => (
              <div
                key={style.id}
                onClick={() => setSelectedStyle(style.id)}
                className={`
                  relative cursor-pointer rounded-xl overflow-hidden transition-all duration-300
                  ${selectedStyle === style.id
                    ? 'ring-2 ring-indigo-500 ring-offset-2 scale-105 shadow-lg'
                    : 'hover:scale-102 hover:shadow-md opacity-75 hover:opacity-100'
                  }
                `}
              >
                <div className={`h-24 bg-gradient-to-br ${styleGradients[style.id] || 'from-gray-400 to-gray-600'}`} />
                <div className="p-3 bg-white">
                  <div className="font-medium text-sm text-slate-700">{style.name}</div>
                  <div className="text-xs text-slate-400 mt-0.5 line-clamp-2">{style.description}</div>
                </div>
                {selectedStyle === style.id && (
                  <div className="absolute top-2 right-2 w-5 h-5 bg-indigo-500 rounded-full flex items-center justify-center">
                    <span className="text-white text-xs">✓</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 表单 */}
      <Card className="!rounded-xl !border-slate-200/60 !shadow-sm">
        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{
            duration: 60,
            language: 'zh',
            auto_approve: true,
          }}
        >
          <Form.Item
            name="prompt"
            label="故事描述"
            rules={[
              { required: true, message: '请输入故事描述' },
              { min: 10, message: '至少输入 10 个字符' },
              { max: 5000, message: '最多 5000 个字符' },
            ]}
          >
            <TextArea
              rows={5}
              placeholder="描述你想要生成的短剧内容，可以包括角色、场景、情节等..."
              showCount
              maxLength={5000}
              className="!rounded-lg"
            />
          </Form.Item>

          <Form.Item name="title" label="自定义标题（可选）">
            <Input placeholder="不填则由 AI 自动生成" maxLength={100} className="!rounded-lg" />
          </Form.Item>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Form.Item name="duration" label="目标时长（秒）">
              <Slider min={15} max={180} step={5} marks={{ 15: '15s', 60: '60s', 120: '120s', 180: '180s' }} />
            </Form.Item>

            <Form.Item name="language" label="语言">
              <Radio.Group>
                <Radio.Button value="zh">中文</Radio.Button>
                <Radio.Button value="en">English</Radio.Button>
                <Radio.Button value="ja">日本語</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </div>

          <Form.Item name="auto_approve" label="自动审批" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
          <p className="text-xs text-slate-400 -mt-4 mb-6">
            关闭后，剧本生成完成将暂停等待你的人工审核
          </p>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              icon={<SendOutlined />}
              loading={createMutation.isPending}
              className="!h-12 !px-10 !rounded-lg !font-semibold"
            >
              开始生成
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
