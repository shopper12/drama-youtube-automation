import { PageShell } from "../components/PageShell";

export default function Dashboard() {
  return (
    <PageShell title="Dashboard" description="제작과 저작권 상태를 한 화면에서 확인합니다.">
      <section className="grid">
        {[
          ["등록 작품", "0"],
          ["허락 대기", "0"],
          ["제작 진행", "0"],
          ["공개 가능", "0"]
        ].map(([label, value]) => (
          <div className="card" key={label}><div className="label">{label}</div><div className="metric">{value}</div></div>
        ))}
      </section>
    </PageShell>
  );
}
