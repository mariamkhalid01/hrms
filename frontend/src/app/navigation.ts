import { LayoutDashboard, Workflow, Timer, GitBranch, Lightbulb } from 'lucide-react';

export const navigation = [
  { path: '/overview', label: 'Overview', shortLabel: 'Overview', icon: LayoutDashboard, description: 'A clear view of your HR process performance.' },
  { path: '/process-explorer', label: 'Process Explorer', shortLabel: 'Process map', icon: Workflow, description: 'Explore the flow, compare paths, and see where time is spent.' },
  { path: '/bottlenecks', label: 'Bottleneck Analysis', shortLabel: 'Bottlenecks', icon: Timer, description: 'Find unusual delays and repeated work worth investigating. Open a finding to see the evidence.' },
  { path: '/variants', label: 'Process paths', shortLabel: 'Process paths', icon: GitBranch, description: 'The same process can follow different routes. Compare the paths your cases actually took.' },
  { path: '/recommendations', label: 'Recommendations', shortLabel: 'Recommendations', icon: Lightbulb, description: 'Decide what to investigate next. Open a suggestion for its evidence and a practical review plan.' },
] as const;
