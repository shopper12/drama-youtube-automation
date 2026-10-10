"use client";

import { useEffect, useState } from "react";
import { PageShell } from "../../components/PageShell";

type Drama = { id: number; title: string; rights_status: string };
type Project = { id: number; drama_id: number; drama_title: string; production_status: string; public_gate: string };
type Scene = { source_id: number; episode_number: number; start_seconds: number; end_seconds: number; event: string; importance: number; confidence: number };
type Source = { id: number; episode_number: number; filename: string; duration_seconds: number; status: string; error_message: string | null; analysis_result: { scenes: Scene[] } | null };
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function MediaProduction() {
  const [token, setToken] = useState("");
  const [dramas, setDramas] = useState<Drama[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [dramaId, setDramaId] = useState("");
  const [episode, setEpisode] = useState("1");
  const [file, setFile] = useState<File | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [timeline, setTimeline] = useState<Scene[]>([]);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const project = projects.find(p => String(p.drama_id) === dramaId);

  async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (token) headers.set("X-Media-Admin-Token", token);
    const response = await fetch(api + endpoint, { ...options, headers, cache: "no-store" });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const detail = typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail) : response.statusText;
      throw new Error(detail);
    }
    return response.json() as Promise<T>;
  }

  async function refresh() {
    try {
      const [d, p] = await Promise.all([
        request<Drama[]>("/dramas"), request<Project[]>("/videos"),
      ]);
      setDramas(d);
      setProjects(p);
      if (!dramaId && d.length) setDramaId(String(d[0].id));
    } catch (err) { setMessage(String(err)); }
  }
  async function refreshSources() {
    if (!dramaId || !token) return;
    try {
      const s = await request<Source[]>(`/media/dramas/${dramaId}/sources`);
      setSources(s);
      const p = projects.find(item => String(item.drama_id) === dramaId);
      if (p) {
        const t = await request<{ scene_plan: Scene[] }>(`/media/projects/${p.id}/timeline`);
        setTimeline(t.scene_plan);
      }
    } catch (err) { setMessage(String(err)); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { void refreshSources(); }, [dramaId, token, projects.length]);

  async function act(name: string, action: () => Promise<unknown>) {
    setWorking(true);
    setMessage(`${name} 처리 중…`);
    try { await action(); setMessage(`${name}: 요청 완료 (화면을 새로고침하여 작업 결과를 확인)`); await refreshSources(); await refresh(); }
    catch (err) { setMessage(`${name} 실패: ${String(err)}`); }
    finally { setWorking(false); }
  }
  const jsonPost = (url: string, payload: object = {}) => request(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });

  return (
    <PageShell title="AI 드라마 영상 제작" description="회차별 원본 업로드 → Gemini 사건 분석 → 장면 선택 → 내레이션 → 로컬 검수용 영상">
      <section className="card" style={{ display: "grid", gap: 12 }}>
        <label>관리자 토큰 (페이지 메모리에만 저장, 브라우저 저장소에 보관하지 않음)
          <input type="password" value={token} onChange={e => setToken(e.target.value)}
            placeholder="MEDIA_ADMIN_TOKEN" style={{ display: "block", width: "100%", padding: 12 }} />
        </label>
        <label>드라마
          <select value={dramaId} onChange={e => setDramaId(e.target.value)} style={{ marginLeft: 10, padding: 8 }}>
            <option value="">선택하세요</option>
            {dramas.map(d => <option key={d.id} value={d.id}>{d.title} ({d.rights_status})</option>)}
          </select>
        </label>
        <label>회차 <input type="number" min={1} value={episode} onChange={e => setEpisode(e.target.value)}
          style={{ width: 70, padding: 8, marginLeft: 8 }} /></label>
        <input type="file" accept=".mp4,.mov,.m4v,.webm" onChange={e => setFile(e.target.files?.[0] || null)} />
        <label>
          <input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} />
          {" "}이 영상 파일을 AI 분석 서비스로 전송·처리할 권한이 있음을 확인합니다. (공개 사용허락과 별개)
        </label>
        <div className="steps">
          <button disabled={working || !file || !dramaId || !authorized || !token || !Number(episode)}
            onClick={() => void act("영상 업로드", async () => {
              const body = new FormData();
              body.append("file", file!);
              body.append("episode_number", episode);
              body.append("analysis_authorized", "true");
              await request(`/media/dramas/${dramaId}/sources`, { method: "POST", body });
            })}>원본 업로드</button>
          <button disabled={working} onClick={() => void refreshSources()}>상태 새로고침</button>
        </div>
        {message && <p role="status">{message}</p>}
      </section>

      <h2>회차별 분석</h2>
      <section className="grid">
        {sources.map(s => <article key={s.id} className="card">
          <strong>{s.episode_number}화 · {s.filename}</strong>
          <p>상태: {s.status} · {Math.round(s.duration_seconds / 60)}분</p>
          <p>{s.analysis_result?.scenes.length ?? 0}개 중요 장면</p>
          {s.error_message && <p style={{ color: "#ff8fa1" }}>{s.error_message}</p>}
          <button disabled={working || !token || s.status === "PROCESSING"}
            onClick={() => void act("AI 분석 시작", () => jsonPost(`/media/sources/${s.id}/analyze`))}>분석/재분석</button>
        </article>)}
      </section>

      <h2>선정 장면 타임라인</h2>
      <section className="card" style={{ overflowX: "auto" }}>
        <table><thead><tr><th>회차</th><th>시작~끝(초)</th><th>중요도</th><th>내용</th></tr></thead>
          <tbody>{timeline.map((s, i) => <tr key={i}>
            <td>{s.episode_number}</td><td>{s.start_seconds}~{s.end_seconds}</td>
            <td>{s.importance}/5</td><td>{s.event}</td>
          </tr>)}</tbody></table>
        {!timeline.length && <p>분석된 장면이 없습니다.</p>}
      </section>

      <h2>제작 · 편집</h2>
      <section className="card">
        <p>프로젝트: {project ? `#${project.id} ${project.drama_title}` : "아직 없음"}</p>
        <p>제작 상태: {project?.production_status || "-"} · 공개 게이트: {project?.public_gate || "-"}</p>
        <div className="steps">
          <button disabled={working || !project} onClick={() => void act("줄거리 구성", () => jsonPost(`/media/projects/${project!.id}/storyboard`, { seconds_budget: 360 }))}>1. 줄거리 구성</button>
          <button disabled={working || !project} onClick={() => void act("TTS 생성", () => jsonPost(`/media/projects/${project!.id}/narrate`))}>2. 한국어 TTS</button>
          <button disabled={working || !project} onClick={() => void act("영상 합성", () => jsonPost(`/media/projects/${project!.id}/assemble`, { seconds_budget: 360 }))}>3. 로컬 영상 제작</button>
          <button disabled={working || !project} onClick={() => void act("전과정", () => jsonPost(`/media/projects/${project!.id}/produce`, { seconds_budget: 360 }))}>한 번에 제작</button>
        </div>
        <p className="caption">원본 영상 클립은 사용허락 범위 확인 후에만 합성됩니다. 이 화면은 유튜브 공개를 실행하지 않습니다.</p>
      </section>
    </PageShell>
  );
}
