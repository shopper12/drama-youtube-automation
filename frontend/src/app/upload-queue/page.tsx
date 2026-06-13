import { PageShell } from "../../components/PageShell";
import { UploadCard } from "../../components/UploadCard";
export default function Page() {
  return <PageShell title="Upload Queue" description="ALLOWED 상태에서만 공개 동작이 활성화됩니다."><section className="grid"><UploadCard title="샘플 프로젝트" /><UploadCard title="거절 예시" gate="BLOCKED_REJECTED" /></section></PageShell>;
}
