import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu } from 'antd';
import {
  HomeOutlined,
  PlusCircleOutlined,
  ProjectOutlined,
} from '@ant-design/icons';

const { Header, Content } = AntLayout;

const menuItems = [
  { key: '/', icon: <HomeOutlined />, label: '首页' },
  { key: '/create', icon: <PlusCircleOutlined />, label: '创建项目' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目列表' },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = menuItems.find(
    (item) => item.key !== '/' && location.pathname.startsWith(item.key),
  )?.key ?? '/';

  return (
    <AntLayout className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <Header className="!bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50 !px-8 flex items-center shadow-sm">
        <div className="flex items-center gap-3 mr-8 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">AI</span>
          </div>
          <span className="text-lg font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            Film Studio
          </span>
        </div>
        <Menu
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          className="flex-1 border-none !bg-transparent"
        />
      </Header>
      <Content className="p-6 md:p-8 max-w-7xl mx-auto w-full">
        <Outlet />
      </Content>
    </AntLayout>
  );
}
