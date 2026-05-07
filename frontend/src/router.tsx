import { createBrowserRouter } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Create from './pages/Create';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import Result from './pages/Result';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'create', element: <Create /> },
      { path: 'projects', element: <ProjectList /> },
      { path: 'projects/:id', element: <ProjectDetail /> },
      { path: 'projects/:id/result', element: <Result /> },
    ],
  },
]);
