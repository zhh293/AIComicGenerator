import { create } from 'zustand';
import type { ProjectDetail } from '../api/types';

interface ProjectStore {
  currentProject: ProjectDetail | null;
  setCurrentProject: (project: ProjectDetail | null) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),
}));
