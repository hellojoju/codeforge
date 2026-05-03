import { ApprovalCenter } from '@/components/ralph/approval-center';

export const metadata = {
  title: '审批中心 - Ralph Runtime Console',
  description: '管理和审批 Ralph Runtime 中的待处理操作和阻塞项',
};

export default function ApprovalsPage() {
  return (
    <div className="h-full">
      <ApprovalCenter />
    </div>
  );
}
